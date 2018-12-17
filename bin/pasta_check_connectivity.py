"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2018

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import os
import sys

from logging import getLogger

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *

log = getLogger(__name__[-15:])


def check_connectivity(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Check result connectivity')

    parser.add_argument('-d', dest='d', default=False, action='store_true')

    args = parser.parse_args(argv)
    repo = config.repo
    f_patch_groups, patch_groups = config.load_patch_groups()

    keys = patch_groups.get_keys()
    for elem in keys:
        if elem not in repo:
            if args.d:
                log.info('Woof woof, removing: %s' % elem)
                patch_groups.remove_key(elem)
            else:
                log.info('Woof woof, not reachable: %s' % elem)

    if args.d:
        patch_groups.optimize()
        patch_groups.to_file(f_patch_groups)
