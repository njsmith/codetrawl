# This file is part of Codetrawl
# Copyright (C) 2015 Nathaniel Smith <njs@pobox.com>
# See file LICENSE.txt for license information.

import sys
import re
import cgi
from collections import defaultdict
import os.path

import jinja2

from .read import read_matches

class group(object):
    def __init__(self, name, filters):
        self.name = name
        self.filters = filters

class filter(object):
    def __init__(self, type_, pattern, comment=None):
        self.type = type_
        self.pattern = pattern
        self._re = re.compile(pattern)
        self.comment = comment

    def check(self, match, line):
        if self.type == "line":
            return self._re.search(line)
        elif self.type == "path":
            return self._re.search("/" + match["path"])
        else:
            return self._re.search(match[self.type])

class FileMetadata(object):
    def __init__(self, repo, path, raw_url):
        self.repo = repo
        self.path = path
        self.raw_url = raw_url

# Given a regex and a large multi-line string, efficiently yield all lines in
# the string that contain a match for the regex
def lines_with_matches(regex, data):
    for match in regex.finditer(data):
        start = data.rfind("\n", 0, match.start())
        # if found, points to the \n, so we want the next character
        # if not found, returns -1, so adding one -> 0 which is correct
        start += 1
        end = data.find("\n", match.end())
        if end == -1:
            end = len(data)
        yield data[start:end]

def make_report(main_pattern, in_paths, out_html_path, groups):
    main_pattern_re = re.compile(main_pattern)

    flat_groups = []
    for g in groups:
        for f in g.filters:
            flat_groups.append((g, f))

    # [group][filter][line_text].append(matching file)
    group_lines = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    # [line_text].append(matching_file)
    leftovers = defaultdict(list)
    queries = defaultdict(int)

    for i, match in enumerate(read_matches(in_paths)):
        sys.stderr.write("\r{}".format(i))

        queries[match["service"], match["query"]] += 1

        fm = FileMetadata(match["repo"], match["path"], match["raw_url"])
        for line_str in lines_with_matches(main_pattern_re, match["content"]):
            line_str = line_str.strip()
            for g, f in flat_groups:
                if f.check(match, line_str):
                    group_lines[g][f][line_str].append(fm)
                    break
            else:
                leftovers[line_str].append(fm)

    sys.stderr.write("...done.\n")

    group_total_counts = defaultdict(int)
    for g in groups:
        for f in g.filters:
            group_total_counts[g] += len(group_lines[g][f])

    template_path = os.path.join(os.path.dirname(__file__),
                                 "_report_template.html")
    env = jinja2.Environment(
        # Looks in the templates/ directory of the 'codetrawl' package
        loader=jinja2.PackageLoader("codetrawl"),
        # http://jinja.pocoo.org/docs/dev/api/#autoescaping
        autoescape=True,
        extensions=["jinja2.ext.autoescape"],
        )

    # arbitrary ids for all the objects to make it easy to show/hide stuff
    from itertools import count
    c = count()
    def gensym():
        return "node-{}".format(c.next())
    ids = {}
    for g in groups:
        ids[g] = gensym()
        for f in g.filters:
            ids[g, f] = gensym()
            for line_text in group_lines[g][f]:
                ids[(g, f), line_text] = gensym()
    for line in leftovers:
        ids["leftovers", line] = gensym()

    template = env.get_template("report.html")
    with open(out_html_path, "w") as out:
        out.write(template.render(main_pattern=main_pattern,
                                  in_paths=in_paths,
                                  queries=queries,
                                  groups=groups,
                                  group_lines=group_lines,
                                  group_total_counts=group_total_counts,
                                  leftovers=leftovers,
                                  ids=ids,
                                  ))
    sys.stderr.write("Report written to: {}\n".format(out_html_path))
