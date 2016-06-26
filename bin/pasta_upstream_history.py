#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import argparse
import functools
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *


def upstream_duration(repo, date_selector, patch_group):
    first_stack_relase = min(map(lambda x: date_selector(x), patch_group))
    upstream_date = repo[patch_group.property].commit_date

    delta = first_stack_relase - upstream_date
    return delta


def pasta_upstream_history(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='Interactive Rating: Rate evaluation results')
    parser.add_argument('-pg', dest='pg_filename', metavar='filename',
                        default=config.patch_groups, help='Patch group file')
    parser.add_argument('-ds', dest='date_selector', default='SRD', choices=['SRD', 'CD'],
                        help='Date selector: Either Commit Date or Stack Release Date (default: %(default)s)')
    args = parser.parse_args(argv)

    patch_groups = EquivalenceClass.from_file(args.pg_filename, must_exist=True)

    psd = config.psd
    repo = config.repo

    date_selector = get_date_selector(repo, psd, args.date_selector)

    upstream_groups = list(filter(lambda x: x.property, patch_groups))

    upstream_helper = functools.partial(upstream_duration, repo, date_selector)
    upstream_groups = list(map(lambda x: (x, upstream_helper(x)), upstream_groups))

    upstream_groups.sort(key=lambda x: x[1])

    for group, duration in upstream_groups:
        upstream = repo[group.property]
        print('%d\t- %s (%s)' % (duration.days,
                                 upstream.subject,
                                 upstream.author.encode('utf-8').decode('ascii', 'ignore')))


if __name__ == '__main__':
    config = Config(sys.argv[1])
    pasta_upstream_history(config, sys.argv[0], sys.argv[1:])
