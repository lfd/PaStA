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
from PaStA import *


def rate(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='classify results of analysis')

    # Thresholds
    parser.add_argument('-ta', dest='thres_accept', metavar='threshold',
                        type=float, default=config.thresholds.autoaccept,
                        help='Autoaccept threshold (default: %(default)s)')
    parser.add_argument('-ti', dest='thres_interactive', metavar='threshold',
                        type=float, default=config.thresholds.interactive,
                        help='Interactive threshold (default: %(default)s)')
    parser.add_argument('-dlr', dest='thres_diff_lines', metavar='threshold',
                        type=float, default=config.thresholds.diff_lines_ratio,
                        help='Diff lines ratio threshold (default: %(default)s)')
    parser.add_argument('-weight', dest='weight', metavar='weight', type=float,
                        default=config.thresholds.message_diff_weight,
                        help='Heuristic factor for message to diff rating. '
                             '(default: %(default)s)')

    parser.add_argument('-rcd', dest='resp_commit_date', action='store_true',
                        default=False, help='Respect commit date')
    parser.add_argument('-p', dest='enable_pager', action='store_true',
                        default=False, help='Enable pager')
    args = parser.parse_args(argv)

    config.thresholds = Thresholds(args.thres_accept,
                                   args.thres_interactive,
                                   args.thres_diff_lines,
                                   config.thresholds.heading,  # does not matter for interactive rating
                                   config.thresholds.filename,  # does not matter for interactive rating
                                   args.weight)

    repo = config.repo
    evaluation_result = EvaluationResult.from_file(config.f_evaluation_result,
                                                   config.d_false_positives)
    filename = config.f_patch_groups

    if evaluation_result.eval_type == EvaluationType.PatchStack:
        print('Running patch stack rating...')
        patch_groups = config.patch_groups
    elif evaluation_result.eval_type == EvaluationType.Upstream:
        print('Running upstream rating...')
        patch_groups = config.patch_groups
    elif evaluation_result.eval_type == EvaluationType.Mailinglist:
        print('Running mailing list rating...')
        patch_groups = EquivalenceClass.from_file(config.f_similar_mailbox)
        filename = config.f_similar_mailbox
    else:
        raise NotImplementedError('rating for evaluation type is not '
                                  'implemented')

    evaluation_result.interactive_rating(repo, patch_groups,
                                         config.thresholds,
                                         args.resp_commit_date,
                                         args.enable_pager)

    patch_groups.to_file(filename)
    evaluation_result.fp.to_file(config.d_false_positives)


if __name__ == '__main__':
    config = Config(sys.argv[1])
    rate(config, sys.argv[0], sys.argv[2:])
