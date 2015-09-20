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
#         for g in groups:
#             total_count = 0
#             for f in g.filters:
#                 total_count += len(group_stats[g][f])
#             out.write("<h3>Group: {} (%s matching lines</h3>\n"
#                       .format(cgi.escape(g.name), total_count))
#             for f in g.filters:
#                 out.write(
#                     "<h4>Filter: <tt>{}</tt> matches <pre>{}</pre> (%s
#                     matching lines)</h4>\n"
#                     .format(f.type, f.pattern, len(group_stats[g][f])))
#                 if f.comment:
#                     out.write("<p>Comment: {}</p>\n"
#                               .format(cgi.escape(comment)))


#         for i, (line, matches) in enumerate(sorted(lines.items())):
#             out.write("""
#             <p><pre style="display: inline;">{line}</pre>
#             <small><a href="javascript:toggle('#line-{i}');">show/hide matches</a></small>
#             <ul id="line-{i}" class="lines lines-{} lines-{}-{}" style="display: none;">
#             """.format(line=cgi.escape(line).encode("utf-8"), i=i))
#             for match in matches:
#                 out.write("""
#                   <li><a href="{raw_url}">{repo} / {path}</a></li>
#                 """.format(**match))
#             out.write("</ul>\n\n")

#         out.write("</body></html>")


# class Skips(object):
#     def __init__(self, patterns_and_comments):
#         patterns = [p_and_c[0] for p_and_c in patterns_and_comments]
#         comments = [p_and_c[1] for p_and_c in patterns_and_comments]
#         self._comments = comments
#         self._patterns = patterns
#         self._regexes = [re.compile(p) for p in patterns]
#         self._counts = [0] * len(self._patterns)

#     def counts(self):
#         return zip(self._patterns, self._comments, self._counts)

#     def check_and_count(self, target):
#         for i, regex in enumerate(self._regexes):
#             if regex.search(target):
#                 self._counts[i] += 1
#                 return True
#         return False

# def make_report(pattern, in_paths, out_html_path,
#                 skip_repos_matching=[],
#                 skip_paths_matching=[],
#                 skip_files_matching=[],
#                 skip_lines_matching=[]):

#     pattern_re = re.compile(pattern)

#     repo_skips = Skips(skip_repos_matching)
#     path_skips = Skips(skip_paths_matching)
#     file_skips = Skips(skip_files_matching)
#     line_skips = Skips(skip_lines_matching)

#     queries = defaultdict(int)

#     lines = defaultdict(list)

#     for i, match in enumerate(read_matches(in_paths)):
#         sys.stderr.write("\r{}".format(i))

#         queries[match["service"], match["query"]] += 1

#         if repo_skips.check_and_count(match["repo"]):
#             continue
#         if path_skips.check_and_count(match["path"]):
#             continue
#         if file_skips.check_and_count(match["content"]):
#             continue

#         for line in match["content"].split("\n"):
#             # FIXME: would be faster to search the underlying string and then
#             # extract matching lines directly, instead of looping over all
#             # lines, but meh, that sounds like work.
#             if not pattern_re.search(line):
#                 continue
#             if line_skips.check_and_count(line):
#                 continue
#             lines[line.strip()].append(match)
#     sys.stderr.write("...done\n")

#     with open(out_html_path, "w") as out:
#         out.write("""<!doctype html>
#         <html>
#           <head>
#             <meta charset="utf-8"> <!-- a lie but whatever -->
#             <title>Report on lines matching %(pattern)s</title>
#           </head>
#           <body>
#             <script>
#               function toggle_elem(elem) {
#                   if (elem.style.display != "none") {
#                       elem.style.display = "none";
#                   } else {
#                       elem.style.display = "";
#                   }
#               }
#               function toggle(selector) {
#                   var elems = document.querySelectorAll(selector);
#                   for (var i = 0; i < elems.length; ++i) {
#                       toggle_elem(elems[i]);
#                   }
#               }
#             </script>
#             <h1>Report on lines matching <pre>%(pattern)s</pre></h1>
#         """ % {"pattern": cgi.escape(pattern)})

#         out.write("<p>Data files:</p> <ul>\n")
#         for path in in_paths:
#             out.write("  <li> {} </li>".format(cgi.escape(path)))
#         out.write("</ul>\n\n")

#         out.write("<p>Which contain search results for:</p><ul>\n")
#         for (service, query), count in sorted(queries.items()):
#             out.write("  <li><pre style=\"display: inline;\">{}</pre> on {} ({} results)</li>\n"
#                       .format(cgi.escape(query), cgi.escape(service), count))
#         out.write("</ul>\n\n")
#         out.write("<p>Total results: {}</p>\n".format(sum(queries.values())))

#         for name, skip in [("Skipped files in repos matching", repo_skips),
#                            ("Skipped files with paths matching", path_skips),
#                            ("Skipped files with contents matching", file_skips),
#                            ("Skipped lines matching", line_skips)]:
#             if skip.counts():
#                 out.write("<p>{}</p> <ul>\n".format(name))
#                 for pattern, comment, count in skip.counts():
#                     out.write("""
#                     <li><pre style="display: inline;">{}</pre> ({}):
#                     {} hits</li>
#                     """.format(cgi.escape(pattern),
#                                cgi.escape(comment),
#                                count))
#                 out.write("</ul>\n\n")

#         out.write("<h2>Matching lines</h2>\n\n")
#         out.write("""<small>
#         <a href="javascript:toggle('.hideable');">show/hide all</a>
#         </small>""")

#         for i, (line, matches) in enumerate(sorted(lines.items())):
#             out.write("""
#             <p><pre style="display: inline;">{line}</pre>
#             <small><a href="javascript:toggle('#line-{i}');">show/hide matches</a></small>
#             <ul id="line-{i}" class="hideable" style="display: none;">
#             """.format(line=cgi.escape(line).encode("utf-8"), i=i))
#             for match in matches:
#                 out.write("""
#                   <li><a href="{raw_url}">{repo} / {path}</a></li>
#                 """.format(**match))
#             out.write("</ul>\n\n")

#         out.write("</body></html>")
