import sys

from codetrawl import read_matches

for match in read_matches(sys.argv[1:]):
    sys.stdout.write(match["raw_url"])
    sys.stdout.write("\n")
