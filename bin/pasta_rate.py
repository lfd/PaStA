"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2018

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
from pypasta import *

log = getLogger(__name__[-15:])


def rate(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='classify results of analysis')

    # evaluation result and patch groups
    parser.add_argument('-er', dest='er_filename', metavar='filename',
                        default=config.f_evaluation_result,
                        help='Evaluation result PKL filename')
    parser.add_argument('-pg', dest='pg_filename', metavar='filename',
                        default=None, help='Filename for patch groups')

    # Thresholds
    parser.add_argument('-ta', dest='thres_accept', metavar='threshold',
                        type=float, default=config.thresholds.autoaccept,
                        help='Autoaccept threshold (default: %(default)s)')
    parser.add_argument('-ti', dest='thres_interactive', metavar='threshold',
                        type=float, default=config.thresholds.interactive,
                        help='Interactive threshold (default: %(default)s)')
    parser.add_argument('-weight', dest='weight', metavar='weight', type=float,
                        default=config.thresholds.message_diff_weight,
                        help='Heuristic factor for message to diff rating. '
                             '(default: %(default)s)')

    parser.add_argument('-rcd', dest='resp_commit_date', action='store_true',
                        default=False, help='Respect commit date')
    parser.add_argument('-p', dest='enable_pager', action='store_true',
                        default=False, help='Enable pager')

    args = parser.parse_args(argv)

    config.thresholds.autoaccept = args.thres_accept
    config.thresholds.interactive = args.thres_interactive
    config.thresholds.message_diff_weight = args.weight

    repo = config.repo
    evaluation_result = EvaluationResult.from_file(args.er_filename,
                                                   config.d_false_positives)

    f_cluster, cluster = config.load_cluster(f_clustering=args.pg_filename)

    log.info('Starting %s rating for %s analysis' %
             (('mailbox' if evaluation_result.is_mbox else 'patch stack'),
              evaluation_result.eval_type.name))

    evaluation_result.interactive_rating(repo, cluster,
                                         config.thresholds,
                                         args.resp_commit_date,
                                         args.enable_pager)

    cluster.to_file(f_cluster)
    evaluation_result.fp.to_file(config.d_false_positives)
