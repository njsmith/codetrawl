# This file is part of Codetrawl
# Copyright (C) 2015 Nathaniel Smith <njs@pobox.com>
# See file LICENSE.txt for license information.

import gzip
import json

def _open(path):
    if path.endswith(".gz"):
        return gzip.open(path)
    else:
        return open(path)

def read_matches(paths):
    for path in paths:
        with _open(path) as f:
            for line in f:
                yield json.loads(line)
