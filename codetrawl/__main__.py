# This file is part of Codetrawl
# Copyright (C) 2015 Nathaniel Smith <njs@pobox.com>
# See file LICENSE.txt for license information.

"""Usage:
  codetrawl [--cookies=firefox | chrome] SERVICE [--] QUERY

where SERVICE is 'github' or 'searchcode', and QUERY is a search query
string. (And by 'codetrawl' above we mean 'python -m codetrawl'.)

Options:
  --cookies=BROWSER   Pull cookies from BROWSER ('firefox' or 'chrome')
                      (requires browser_cookie package)

Performs the given search on the given code search service, then downloads all
matching files.

If you want to perform searches while logged in on Github, then use your
browser to log in as normal, and then use the --cookies option to tell
codetrawl to use your browser's cookies to authenticate. (Github is more
aggressive about throttling anonymous users than logged-in users, so this
makes things a bit faster.)

For each hit, prints a single-line JSON object to stdout, with keys:
  - service: "github" or "searchcode"
  - query: the query string used
  - repo: an unstructured string indicating the repo
  - path: path to the matching file within this repo
  - raw_url: a URL where the matching file can be downloaded
  - content: the matching file's contents (downloaded from raw_url)

"""

import sys

import docopt
import requests

from .search import SERVICES, dump_all_matches

args = docopt.docopt(__doc__)

service = args["SERVICE"]

if service not in SERVICES:
    sys.exit("service must be one of: {}".format(", ".join(SERVICES)))

session = requests.Session()
if args["--cookies"]:
    try:
        import browser_cookie
    except ImportError:
        sys.exit("pip install browser_cookie if you want browser cookies")
    # browser_cookie is super-annoying and likes to print to stdout
    stdout = sys.stdout
    try:
        sys.stdout = sys.stderr
        if args["--cookies"] == "firefox":
            jar = browser_cookie.firefox()
        elif args["--cookies"] == "chrome":
            jar = browser_cookie.chrome()
        else:
            sys.exit("BROWSER should be 'firefox' or 'chrome'")
    finally:
        sys.stdout = stdout
    session.cookies = jar

dump_all_matches(service, args["QUERY"], sys.stdout, session=session)
