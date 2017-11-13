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

from logging import getLogger

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))
from PaStA import *

log = getLogger(__name__[-15:])


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

    f_patch_groups, patch_groups =\
        config.load_patch_groups(evaluation_result.is_mbox, True)

    log.info('Starting %s rating for %s analysis' %
             (('mailbox' if evaluation_result.is_mbox else 'patch stack'),
              evaluation_result.eval_type.name))

    evaluation_result.interactive_rating(repo, patch_groups,
                                         config.thresholds,
                                         args.resp_commit_date,
                                         args.enable_pager)

    patch_groups.to_file(f_patch_groups)
    evaluation_result.fp.to_file(config.d_false_positives)


if __name__ == '__main__':
    config = Config(sys.argv[1])
    rate(config, sys.argv[0], sys.argv[2:])
