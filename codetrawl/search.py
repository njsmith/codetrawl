# This file is part of Codetrawl
# Copyright (C) 2015 Nathaniel Smith <njs@pobox.com>
# See file LICENSE.txt for license information.

import sys
import json
import re
import time

import requests
from lxml import html

USER_AGENT = "https://github.com/njsmith/codetrawl / njs@pobox.com / using python requests"
BASE_HEADERS = {"User-Agent": USER_AGENT}

# Invariant: the screen always looks like
#   ... stuff ...
#   <tick line>
#              ^ write position is here
class Ticker(object):
    def __init__(self):
        self._tick_line = ""

    def _terminal_width(self):
        # HAAAAACK
        return 75

    def _clear(self):
        sys.stderr.write("\r")
        sys.stderr.write(" " * self._terminal_width())
        sys.stderr.write("\r")

    def say(self, text):
        self._clear()
        sys.stderr.write(text)
        if not text.endswith("\n"):
            sys.stderr.write("\n")
        self._rewrite_tick()

    def _rewrite_tick(self):
        self._clear()
        sys.stderr.write(self._tick_line)

    def update(self, tick_line):
        self._tick_line = tick_line
        self._rewrite_tick()

    def done(self, final_message=""):
        if self._tick_line:
            sys.stderr.write("\n")
        self._tick_line = ""
        sys.stderr.write(final_message)
        if final_message and not final_message.endswith("\n"):
            sys.stderr.write("\n")

    def __del__(self):
        self.done()

TICKER = Ticker()

def _link_targets(tree):
    for a in tree.cssselect("a"):
        if "href" in a.attrib:
            yield a.attrib["href"]

class Error429(Exception):
    pass

def _get(session, *args, **kwargs):
    pause = 1
    backoffs = 0
    start = time.time()
    while True:
        try:
            response = session.get(*args, **kwargs)
            if response.status_code == 429:
                raise Error429()
        except (requests.exceptions.ConnectionError, Error429):
            time.sleep(pause)
            backoffs += 1
            pause *= 2
            continue
        response.raise_for_status()
        end = time.time()
        if backoffs > 0 or end - start > 3:
            TICKER.say("  Slow request: took {:.1f} sec with {} backoffs"
                       .format(end - start, backoffs))
        return response

_github_partial_count_re = re.compile(r"Showing [0-9,]+ available code")
def _github_search_timed_out(tree):

    for h3 in tree.cssselect("h3"):
        for link_target in _link_targets(h3):
            if "searching-github#potential-timeouts" in link_target:
                return True

        if _github_partial_count_re.search(h3.text_content()):
            raise AssertionError("bwuh? contradictory results from two tests "
                                 "of whether search timed out on server side")

def search_github(query, session=None):
    if session is None:
        session = requests.Session()
    # p= page number, 1-100
    # q= search string
    # l= language (or leave off for all languages)
    #    you can also put language: into the search query
    # I don't know what the ref and type arguments do, I just copied them from
    # a real results page.
    base_params = {"ref": "searchresults",
                   "type": "Code",
                   "q": query}
    hits = set()
    page = 1
    server_side_timeouts = 0
    while True:
        params = dict(base_params)
        params["p"] = page
        response = _get(session, "https://github.com/search",
                        params=params,
                        headers=BASE_HEADERS)

        tree = html.fromstring(response.text)
        tree.make_links_absolute(response.request.url)

        if _github_search_timed_out(tree):
            server_side_timeouts += 1
            if server_side_timeouts >= 3:
                raise RuntimeError("Search timed-out on server side 3x in a "
                                   "row, returning only partial results -- "
                                   "try a less expensive query")
            continue
        else:
            server_side_timeouts = 0

        # Find the result count box, which is an h3
        # It should say
        #   We've found 2,758 code results
        # It might instead say
        #   Showing 2,948 available code results
        # together with a little link to
        #   https://help.github.com/articles/searching-github#potential-timeouts
        # which indicates that the search timed out and results may be
        # incomplete.
        #
        # Or, finally, if there were no hits at all, there will be an h3 that
        # says "We couldn't find any code matching ..."
        github_count_re = re.compile(r"found (?P<count>[0-9,]+) code results")

        found_count = 0
        possible_count_texts = []
        for h3 in tree.cssselect("h3"):
            text = h3.text_content()
            possible_count_texts.append(text)

            for match in github_count_re.finditer(text):
                count_str = match.group("count")
                count = int(count_str.replace(",", ""))
                found_count += 1
                if count > 1000:
                    raise RuntimeError("Too many hits! Try a search with"
                                       "<= 1000 results (not {})"
                                       .format(count))
                if count <= len(hits):
                    # We have finished processing this search
                    return

                # Advance to the next page -- or wrap around if we're at the
                # end. (This is necessary because sometimes it takes multiple
                # passes to find all the hits -- the ordering of results is
                # not stable, so a particular hit could be on page 3 when
                # you're requesting page 2, and then switch to page 2 when you
                # request page 3, and you miss it entirely. The only solution
                # I know is to rescan the results several times until you find
                # them all.)
                total_pages = count // 10
                if count % 10:
                    total_pages += 1
                if page == total_pages:
                    TICKER.say("  Finished pass, but only found "
                               "{} of {} hits; scanning again\n"
                               .format(len(hits), count))
                    page = 1
                else:
                    page += 1

            if u"We couldn\u2019t find any code matching" in text:
                # Basically that's a count of 0, and the rest of the scraping
                # will break
                assert page == 1
                return

        if found_count != 1:
            raise RuntimeError("scraper broken -- found {} count strings"
                               "(text: {})"
                               .format(found_count, possible_count_texts))

        # results are in
        #   <div id="code_search_results">
        #     <div class="code-list"> ... </div>
        #     <div class="paginate-container"> (pagination stuff) </div>
        #   </div>
        #
        # on a past-the-end page, the code list div contains only whitespace

        # easiest way to find result links is to find links that look like
        #   <a
        #   href="/dch312/numpy/blob/fbcc24fa7cedd2bbf25506a0683f89d13f2d4846/doc/source/reference/c-api.array.rst" ...>
        #
        # and make sure to throw away fragments and deduplicate
        #
        #  /(.*)/blob/[0-9a-f]{40}/(.*)
        #
        # first group is reponame, second group is path
        # replace /blob/ with /raw/ to get the raw text

        result_url_re = re.compile(
            r"https://github.com/"
            r"(?P<repo>.*)"
            r"/blob/[0-9a-f]{40}/"
            r"(?P<path>.*)")

        (results_div,) = tree.cssselect("#code_search_results > .code-list")
        for url in _link_targets(results_div):
            # Discard fragments (these appear on links to specific lines)
            url = url.split("#")[0]
            match = result_url_re.match(url)
            if match:
                raw_url = url.replace("/blob/", "/raw/")
                if raw_url not in hits:
                    hits.add(raw_url)
                    yield {"repo": "github:" + match.group("repo"),
                           "path": match.group("path"),
                           "raw_url": raw_url}

def search_searchcode(query, session=None):
    if session is None:
        session = requests.Session()
    page = 0
    while True:
        response = _get(session,
                        "https://searchcode.com/api/codesearch_I",
                        params={"q": query,
                                "per_page": 100,
                                "p": page},
                        headers=BASE_HEADERS)
        response.raise_for_status()
        payload = json.loads(response.text or response.content)
        if payload["page"] != page:
            # Probably ran off the end
            raise RuntimeError("Too many results")
        page += 1

        if not payload["results"]:
            # End-of-results is signalled by an empty results page
            break

        for result in payload["results"]:
            repo = result["repo"]
            path = result["location"] + "/" + result["filename"]
            raw_url = result["url"].replace("/view/", "/raw/")
            yield {"repo": repo, "path": path, "raw_url": raw_url}

SERVICES = {
    "github": search_github,
    "searchcode": search_searchcode,
}

def dump_all_matches(service, query, out_file, session=None):
    if session is None:
        session = requests.Session()

    search_fn = SERVICES[service]

    TICKER.say("Searching for {!r} on {}".format(query, service))

    for i, match in enumerate(search_fn(query, session=session)):
        TICKER.update("  Fetching file #{}".format(i + 1))
        try:
            r = _get(session, match["raw_url"])
        except requests.HTTPError as e:
            TICKER.say("  Error fetching {}: {}".format(match["raw_url"], e))
            TICKER.update("  Failed to fetch file #{}".format(i + 1))
        else:
            TICKER.update("  Fetched file #{}, searching for more"
                          .format(i + 1))
        match["service"] = service
        match["query"] = query
        match["content"] = r.content

        encoded = json.dumps(match)
        assert "\n" not in encoded
        out_file.write(encoded)
        out_file.write("\n")
    TICKER.done("Finished search for {!r} on {}".format(query, service))
