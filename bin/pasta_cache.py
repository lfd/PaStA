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
from pypasta import *


def parse_choices(config, choices):
    stack = upstream = mbox = False

    if choices:
        if choices == 'downstream' or choices == 'all':
            if config.mode == Config.Mode.MBOX:
                mbox = True
            elif config.mode == Config.Mode.PATCHSTACK:
                stack = True

        if choices == 'upstream' or choices == 'all':
            upstream = True

    return stack, upstream, mbox


def remove_if_exist(filename):
    if os.path.isfile(filename):
        os.remove(filename)


def cache(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='create commit cache')

    choices = ['downstream', 'upstream', 'all']
    parser.add_argument('-create', metavar='create', default=None,
                        choices=choices,
                        help='create cache for commits on patch stacks or '
                             'mailboxes (downstream) and upstream commits')
    parser.add_argument('-clear', metavar='clear', default=None, choices=choices)

    args = parser.parse_args(argv)
    repo = config.repo

    create_stack, create_upstream, create_mbox = parse_choices(config, args.create)
    clear_stack, clear_upstream, clear_mbox = parse_choices(config, args.clear)

    if clear_stack:
        remove_if_exist(config.f_ccache_stack)
    if clear_upstream:
        remove_if_exist(config.f_ccache_upstream)
    if clear_mbox:
        remove_if_exist(config.f_ccache_mbox)

    if create_stack:
        repo.load_ccache(config.f_ccache_stack)
        repo.cache_commits(config.psd.commits_on_stacks)
        repo.export_ccache(config.f_ccache_stack)
        repo.clear_commit_cache()
    if create_upstream:
        repo.load_ccache(config.f_ccache_upstream)
        repo.cache_commits(config.upstream_hashes)
        repo.export_ccache(config.f_ccache_upstream)
        repo.clear_commit_cache()
    if create_mbox:
        config.repo.register_mailbox(config.d_mbox)

        repo.load_ccache(config.f_ccache_mbox)
        repo.cache_commits(repo.mbox.message_ids())
        repo.export_ccache(config.f_ccache_mbox)
        repo.clear_commit_cache()


if __name__ == '__main__':
    config = Config(sys.argv[1])
    cache(config, sys.argv[0], sys.argv[2:])
