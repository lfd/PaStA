"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import functools
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *


def upstream_duration(repo, date_selector, cluster, rep):
    group = cluster.get_untagged(rep)
    upstream = get_first_upstream(repo, cluster, rep)

    first_stack_relase = min(map(lambda x: date_selector(x), group))
    upstream_date = repo[upstream].commit.date

    delta = first_stack_relase - upstream_date
    return delta


def pasta_upstream_history(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Interactive Rating: Rate '
                                                 'evaluation results')
    parser.add_argument('-ds', dest='date_selector', default='SRD',
                        choices=['SRD', 'CD'],
                        help='Date selector: Either Commit Date or Stack Release'
                             ' Date (default: %(default)s)')
    args = parser.parse_args(argv)

    config.fail_no_patch_groups()
    # !FIXME Not align with current API
    cluster = config.patch_groups
    psd = config.psd
    repo = config.repo

    date_selector = get_date_selector(repo, psd, args.date_selector)

    groups_with_upstream = set()
    for group in cluster:
        rep = list(group)[0]
        if cluster.get_tagged(rep):
            groups_with_upstream.add(rep)


    upstream_helper = functools.partial(upstream_duration, repo, date_selector,
                                        cluster)
    upstream_groups = list(map(lambda x: (x, upstream_helper(x)),
                               groups_with_upstream))

    upstream_groups.sort(key=lambda x: x[1])

    for rep, duration in upstream_groups:
        upstream = repo[get_first_upstream(repo, cluster, rep)]
        print('%d\t- %s (%s)' % (duration.days,
                                 upstream.subject,
                                 upstream.author.encode('utf-8').decode('ascii', 'ignore')))
