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


def optimise_cluster(argv):
    parser = argparse.ArgumentParser(prog='optimise_cluster',
                                     description='Optimise a clustering')
    parser.add_argument('clustering', metavar='clustering', type=str,
                        help='Equivalence class file')

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return

    try:
        res = Clustering.from_file(args.clustering, must_exist=True)
    except Exception as e:
        log.error('optimise_cluster: %s' % str(e))
        return

    res.optimize()
    res.to_file(args.clustering)
