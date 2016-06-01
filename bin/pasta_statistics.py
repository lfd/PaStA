#!/usr/bin/env python3

import argparse
import os
from subprocess import call
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *


def statistics(prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='Interactive Rating: Rate evaluation results')
    parser.add_argument('-pg', dest='pg_filename', metavar='filename',
                        default=config.patch_groups, help='Patch group file')
    parser.add_argument('-R', dest='r_resources', metavar='directory',
                        default=config.R_resources, help='Output directory for R resources')
    parser.add_argument('-ds', dest='date_selector', default='SRD', choices=['SRD', 'CD'],
                        help='Date selector: Either Commit Date or Stack Release Date (default: %(default)s)')
    parser.add_argument('-noR', dest='R', action='store_false', help='Don\'t invoke R')
    parser.set_defaults(R=True)
    args = parser.parse_args(argv)

    patch_groups = EquivalenceClass.from_file(args.pg_filename, must_exist=True)

    r_resources = args.r_resources
    if not os.path.exists(r_resources):
        os.makedirs(r_resources)

    release_sort_filename = os.path.join(r_resources, "release-sort")
    mainline_release_dates_filename = os.path.join(r_resources, 'mainline-release-dates')
    stack_release_dates_filename = os.path.join(r_resources, 'stack-release-dates')
    patches_filename = os.path.join(r_resources, 'patches')
    upstream_filename = os.path.join(r_resources, 'upstream')
    occurrence_filename = os.path.join(r_resources, 'patch-occurrence')

    date_selector = get_date_selector(args.date_selector)

    # Export sorted list of release names
    export_sorted_release_names(release_sort_filename)

    # Export release dates
    export_release_dates(mainline_release_dates_filename,
                         stack_release_dates_filename)

    # Export information of patch groups
    export_patch_groups(upstream_filename,
                        patches_filename,
                        occurrence_filename,
                        patch_groups, date_selector)

    if args.R:
        call(['./R/PaStA.R',
              config.project_name,
              r_resources,
              release_sort_filename,
              mainline_release_dates_filename,
              stack_release_dates_filename,
              patches_filename,
              upstream_filename,
              occurrence_filename])

if __name__ == '__main__':
    statistics(sys.argv[0], sys.argv[1:])
