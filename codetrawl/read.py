# This file is part of Codetrawl
# Copyright (C) 2015 Nathaniel Smith <njs@pobox.com>
# See file LICENSE.txt for license information.

import json

def read_matches(paths):
    for path in paths:
        with open(path) as f:
            for line in f:
                yield json.loads(line)
