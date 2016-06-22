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
import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *
from PaStA.PatchStack import export_commit_cache, clear_commit_cache


def cache(prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='create commit cache')

    parser.add_argument('-stack', action='store_true', default=False,
                        help='create cache for commits on patch stacks')
    parser.add_argument('-upstream', action='store_true', default=False,
                        help='create cache for upstream commits')
    parser.add_argument('-all', action='store_true', default=False,
                        help='create cache for upstream and patch stack commits')
    parser.add_argument('-mbox', metavar='filename', default=None,
                        help='create cache for mailbox')
    parser.add_argument('-mindate', dest='mindate', metavar='mindate', default=config.mbox_mindate,
                        help='Skip mails older than mindate (only together with -mbox, default: %(default)s)')
    parser.add_argument('-maxdate', dest='maxdate', metavar='maxdate', default=config.mbox_maxdate,
                        help='Skip mails older than mindate (only together with -mbox, default: %(default)s)')

    args = parser.parse_args(argv)

    if args.all:
        args.stack = True
        args.upstream = True

    if args.stack:
        load_commit_cache(config.commit_cache_stack_filename, must_exist=False)
        cache_commits(patch_stack_definition.commits_on_stacks)
        export_commit_cache(config.commit_cache_stack_filename)
        clear_commit_cache()
    if args.upstream:
        load_commit_cache(config.commit_cache_upstream_filename, must_exist=False)
        cache_commits(patch_stack_definition.upstream_hashes)
        export_commit_cache(config.commit_cache_upstream_filename)
        clear_commit_cache()
    if args.mbox:
        ids = get_commits_from_file(config.mailbox_id_filename, ordered=False, must_exist=False)
        mindate = datetime.datetime.strptime(args.mindate, "%Y-%m-%d")
        maxdate = datetime.datetime.strptime(args.maxdate, "%Y-%m-%d")
        ids |= load_and_cache_mbox(args.mbox, mindate, maxdate)
        with open(config.mailbox_id_filename, 'w') as f:
            f.write('\n'.join(ids) + '\n')
        export_commit_cache(config.commit_cache_mbox_filename)


if __name__ == '__main__':
    cache(sys.argv[0], sys.argv[1:])
