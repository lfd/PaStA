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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *


def optimise_cluster(argv):
    parser = argparse.ArgumentParser(prog='optimise_cluster',
                                     description='Optimise a clustering')
    parser.add_argument('clustering', metavar='clustering', type=str,
                        help='Equivalence class file')

    args = parser.parse_args(argv)

    res = Clustering.from_file(args.clustering, must_exist=True)
    res.optimize()
    res.to_file(args.clustering)
