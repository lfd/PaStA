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

from subprocess import call

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))
from pypasta import *


def statistics(config, argv):
    parser = argparse.ArgumentParser(prog='statistics', description='Interactive Rating: Rate evaluation results')
    parser.add_argument('-ds', dest='date_selector', default='SRD', choices=['AD', 'CD', 'SRD'],
                        help='Date selector: Either Author Date, Commit Date or Stack Release Date (default: %(default)s)')
    parser.add_argument('-noR', dest='R', action='store_false', help='Don\'t invoke R')
    parser.add_argument('-noEx', dest='Ex', action='store_false', help='Don\'t export data')
    parser.set_defaults(R=True)
    args = parser.parse_args(argv)

    # !FIXME Not aligned with current API
    _, cluster = config.load_cluster()
    psd = config.psd
    repo = config.repo

    d_R = config.d_R
    if not os.path.exists(d_R):
        os.makedirs(d_R)

    release_sort_filename = os.path.join(d_R, "release-sort")
    mainline_release_dates_filename = os.path.join(d_R, 'mainline-release-dates')
    stack_release_dates_filename = os.path.join(d_R, 'stack-release-dates')
    patches_filename = os.path.join(d_R, 'patches')
    upstream_filename = os.path.join(d_R, 'upstream')
    occurrence_filename = os.path.join(d_R, 'patch-occurrence')
    diffstat_filename = os.path.join(d_R, 'diffstat')

    date_selector = get_date_selector(repo, psd, args.date_selector)

    export = Export(repo, psd)

    if args.Ex:
        # Export sorted list of release names
        print('Exporting sorted release names...')
        export.sorted_release_names(release_sort_filename)

        # Export release dates
        print('Exporting release dates...')
        export.release_dates(mainline_release_dates_filename,
                             stack_release_dates_filename)

        # If the date_selector is not Stack Release Date (SRD), cache all
        # commits of the patch stacks, as we need date information of each
        # of them
        if args.date_selector != 'SRD':
            config.load_ccache_stack()
            repo.cache_commits(psd.commits_on_stacks)

        # Export information of patch groups
        print('Exporting patch groups...')
        export.patch_groups(upstream_filename,
                            patches_filename,
                            occurrence_filename,
                            cluster, date_selector)

        # Export diffstat (cloccount across patch stack releases)
        print('Exporting diffstats...')
        export.diffstat(diffstat_filename)

    if args.R:
        print('Invoke R')
        call(['./analyses/PaStA.R', d_R])
