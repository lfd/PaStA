#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *


def compare(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='create commit cache')

    parser.add_argument('-mbox', action='store_true', default=False,
                        help='Also load mbox cache')
    parser.add_argument('-n', action='store_false', default=True,
                        help = 'don\'t use a pager')
    parser.add_argument('commits', metavar='commit', type=str, nargs='+',
                        help='Commit hashes / Mail IDs')
    args = parser.parse_args(argv)

    commits = args.commits

    repo = config.repo
    if args.mbox:
        repo.load_commit_cache(config.commit_cache_mbox_filename, must_exist=True)

    if len(commits) == 1:
        show_commit(repo, commits[0])
        return

    for i in range(len(commits)-1):
        commit_a = commits[i]
        commit_b = commits[i+1]

        show_commits(repo, commit_a, commit_b, args.n)

        rating = preevaluate_commit_pair(repo, commit_a, commit_b)
        if rating:
            print('Preevaluation: Possible candidates')
            rating = evaluate_commit_pair(repo, config.thresholds,
                                          commit_a, commit_b)
            print(str(rating.msg) + ' message and ' +
                  str(rating.diff) + ' diff, diff length ratio: ' +
                  str(rating.diff_lines_ratio))
        else:
            print('Preevaluation: Not related')
        getch()

if __name__ == '__main__':
    config = Config(sys.argv[1])
    compare(config, sys.argv[0], sys.argv[2:])
