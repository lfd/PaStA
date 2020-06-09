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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))
from pypasta import *


def show_cluster(config, argv):
    parser = argparse.ArgumentParser(prog='show_cluster', description='compare patches')

    parser.add_argument('-n', action='store_false', default=True,
                        help = 'don\'t use a pager')
    parser.add_argument('patch', metavar='representative', type=str,
                        help='Commit hash / Mail ID')

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return

    repo = config.repo

    _, cluster = config.load_cluster()

    cluster = list(cluster[args.patch])

    if len(cluster) == 1:
        show_commit(repo, cluster[0])
        return

    for i in range(len(cluster)-1):
        patch_a = cluster[i]
        patch_b = cluster[i+1]

        show_commits(repo, patch_a, patch_b, args.n)

        # evaluation type plays no role in this case
        rating = evaluate_commit_list(repo, config.thresholds,
                                      False, None,
                                      [patch_a], [patch_b])
        if rating:
            print(rating[patch_a][0][1])
        else:
            print('Not related')
        getch()
