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


def check_connectivity(config, argv):
    parser = argparse.ArgumentParser(prog='check_connectivity',
                                     description='Check result connectivity')

    parser.add_argument('-d', dest='d', default=False, action='store_true')

    args = parser.parse_args(argv)
    repo = config.repo
    f_cluster, cluster = config.load_cluster()

    keys = cluster.get_all_elements()
    for elem in keys:
        if elem not in repo:
            if args.d:
                log.info('Woof woof, removing: %s' % elem)
                cluster.remove_element(elem)
            else:
                log.info('Woof woof, not reachable: %s' % elem)

    if args.d:
        cluster.optimize()
        cluster.to_file(f_cluster)
