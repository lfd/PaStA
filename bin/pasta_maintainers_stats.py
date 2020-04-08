"""
PaStA - Patch Stack Analysis

Copyright (c) Bayerische Motoren Werke Aktiengesellschaft (BMW AG), 2020
Copyright (c) OTH Regensburg, 2020

Authors:
   Basak Erdamar <basakerdamar@gmail.com>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import os
import pygit2
import sys

from logging import getLogger

sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

log = getLogger(__name__[-15:])


def maintainers_stats(config, argv):
    return
