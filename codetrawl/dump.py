# This file is part of Codetrawl
# Copyright (C) 2015 Nathaniel Smith <njs@pobox.com>
# See file LICENSE.txt for license information.

"""Usage:
  codetrawl.dump PATTERN FILE [FILE...]

where PATTERN is a Python format string like "{raw_url}", with allowed keys:
  - service
  - query
  - repo
  - path
  - raw_url
  - content
"""

import sys

import docopt

from .read import read_matches

if __name__ == "__main__":
    args = docopt.docopt(__doc__)

    for match in read_matches(args["FILE"]):
        sys.stdout.write(args["PATTERN"].format(**match))
        sys.stdout.write("\n")
