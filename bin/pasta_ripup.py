"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

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


def ripup(config, argv):
    parser = argparse.ArgumentParser(prog='ripup',
                                     description='Rip up equivalence class and '
                                                 'reanalyse')

    parser.add_argument('reps', metavar='representative', type=str, nargs='+',
                        help='Representatives of equivalence class. Allows to '
                             'specify multiple classes.')

    parser.add_argument('-cpu', dest='cpu_factor', metavar='cpu', type=float,
                        default=1.0, help='CPU factor for parallelisation '
                                        '(default: %(default)s)')

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
    parser.add_argument('-th', dest='thres_heading', metavar='threshold',
                        default=config.thresholds.heading, type=float,
                        help='Minimum diff hunk section heading similarity '
                             '(default: %(default)s)')
    parser.add_argument('-tf', dest='thres_filename', metavar='threshold',
                        default=config.thresholds.filename, type=float,
                        help='Minimum filename similarity '
                             '(default: %(default)s)')
    parser.add_argument('-adi', dest='thres_adi', metavar='days', type=int,
                        default=config.thresholds.author_date_interval,
                        help='Author date interval (default: %(default)s)')

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return

    representatives = args.reps
    repo = config.repo
    mbox = config.mode == Config.Mode.MBOX

    config.thresholds = Thresholds(args.thres_accept,
                                   args.thres_interactive,
                                   args.thres_diff_lines,
                                   args.thres_heading,
                                   args.thres_filename,
                                   args.weight,
                                   args.thres_adi)

    f_cluster, cluster = config.load_cluster()

    for representative in representatives:
        if representative not in cluster:
            log.error('Not found in any patch group: %s' % representative)
            continue

        elems = cluster.ripup_cluster(representative)

        evaluation_result = evaluate_commit_list(repo, config.thresholds,
                                                 mbox,
                                                 EvaluationType.PatchStack,
                                                 elems, elems,
                                                 parallelise=False,
                                                 verbose=True,
                                                 cpu_factor=args.cpu_factor)

        evaluation_result.load_fp(config.d_false_positives, False)
        evaluation_result.interactive_rating(repo, cluster,
                                             config.thresholds, False, True)
        evaluation_result.fp.to_file(config.d_false_positives)
        cluster.to_file(f_cluster)
