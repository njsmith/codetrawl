# codetrawl
#
# Copyright (C) 2015 Nathaniel J. Smith <njs@pobox.com>
# 2-clause BSD -- see LICENSE.txt for details

import sys
import json
import re
import time
from collections import namedtuple

import requests
from lxml import html

Match = namedtuple("Match", ["repo", "path", "raw_url"])

USER_AGENT = "codetrawl search tool / njs@pobox.com / using python requests"
BASE_HEADERS = {"User-Agent": USER_AGENT}

def _link_targets(tree):
    for a in tree.cssselect("a"):
        if "href" in a.attrib:
            yield a.attrib["href"]

def _get_with_backoff(session, *args, **kwargs):
    pause = 1
    backoffs = 0
    start = time.time()
    while True:
        response = session.get(*args, **kwargs)
        if response.status_code == 429:
            #print(response.text)
            time.sleep(pause)
            backoffs += 1
            pause *= 2
            continue
        else:
            end = time.time()
            print("  request took {:.2f} sec with {} backoffs"
                  .format(end - start, backoffs))
            return response

def search_github(session, query):
    # p= page number, 1-100
    # q= search string
    # l= language (or leave off for all languages)
    #   c
    #   cpp
    #   cython
    #   objective-c
    #   diff
    #   python
    # swig? -- apparently gets detected as C?
    #   e.g. https://github.com/search?l=c&q=PyArray_Dtype+in%3Afile%2Cpath+NOT+numpy%2Fcore+NOT+extras%2Fnumpy_include+NOT+ndarrayobject&ref=searchresults&type=Code&utf8=%E2%9C%93
    #
    # you can also put language: into the search query
    base_params = {"ref": "searchresults",
                   "type": "Code",
                   "q": query}
    for i in range(1, 101):
        params = dict(base_params)
        params["p"] = i
        response = _get_with_backoff(session, "https://github.com/search",
                                     params=params,
                                     headers=BASE_HEADERS)
        response.raise_for_status()

        tree = html.fromstring(response.text)
        tree.make_links_absolute(response.request.url)

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
        github_partial_count_re = re.compile(r"Showing [0-9,] available code")

        found_count = 0
        for h3 in tree.cssselect("h3"):
            for link_target in _link_targets(h3):
                if "searching-github#potential-timeouts" in link_target:
                    raise RuntimeError("Search timed out on server side "
                                       "and returned only partial results")
            text = h3.text_content()
            for match in github_partial_count_re.finditer(text):
                raise RuntimeError("Search seems to have timed out "
                                   "but first check failed! something "
                                   "weird is going on.")
            for match in github_count_re.finditer(text):
                count_str = match.group("count")
                count = int(count_str.replace(",", ""))
                found_count += 1
                if count > 1000:
                    raise RuntimeError("Too many hits! Try a search with"
                                       "<= 1000 results (not {})"
                                       .format(count))
        if found_count != 1:
            raise RuntimeError("scraper broken -- found {} count strings"
                               .format(found_count))

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
        hits = set()
        for url in _link_targets(results_div):
            # Discard fragments (these appear on links to specific lines)
            url = url.split("#")[0]
            match = result_url_re.match(url)
            if match:
                hits.add(Match("github:" + match.group("repo"),
                               match.group("path"),
                               url.replace("/blob/", "/raw/")))

        if not hits:
            # Must have found the end of the results
            break

        for hit in hits:
            yield hit

def search_searchcode(session, query):
    page = 0
    while True:
        response = _get_with_backoff("https://searchcode.com/api/codesearch_I",
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
            url = result["url"].replace("/view/", "/raw/")
            yield Match(repo, path, url)
