#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

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


def compare(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='compare patches')

    parser.add_argument('-n', action='store_false', default=True,
                        help = 'don\'t use a pager')
    parser.add_argument('commits', metavar='commit', type=str, nargs='+',
                        help='Commit hashes / Mail IDs')

    parser.add_argument('-th', dest='thres_heading', metavar='threshold',
                        default=config.thresholds.heading, type=float,
                        help='Minimum diff hunk section heading similarity '
                             '(default: %(default)s)')

    args = parser.parse_args(argv)

    config.thresholds.heading = args.thres_heading
    commits = args.commits
    repo = config.repo

    if any([x.startswith('<') for x in commits]):
        repo.mbox_register(config.d_mbox)

    if len(commits) == 1:
        show_commit(repo, commits[0])
        return

    for i in range(len(commits)-1):
        commit_a = commits[i]
        commit_b = commits[i+1]

        show_commits(repo, commit_a, commit_b, args.n)

        # evaluation type plays no role in this case
        rating = evaluate_commit_list(repo, config.thresholds,
                                      False, None,
                                      [commit_a], [commit_b])
        if rating:
            print(rating[commit_a][0][1])
        else:
            print('Not related')
        getch()


if __name__ == '__main__':
    config = Config(sys.argv[1])
    compare(config, sys.argv[0], sys.argv[2:])
