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


def sync(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Manage PaStA\'s resources')

    choices = ['downstream', 'upstream', 'all']
    parser.add_argument('-create', metavar='create', default=None,
                        choices=choices,
                        help='create cache for commits on patch stacks or '
                             'mailboxes (downstream) and upstream commits. '
                             'Possibilities: downstream / upstream / all')
    parser.add_argument('-clear', metavar='clear', default=None,
                        choices=choices,
                        help='Invalidates cache. Usage same as create')
    parser.add_argument('-mbox', action='store_true', default=False,
                        help='synchronise mailboxes before creating caches')
    parser.add_argument('-noup', action='store_true', default=False,
                        help='Don\'t synchronise upstream repositories')
    parser.add_argument('-nofetch', action='store_true', default=False,
                        help='Don\'t fetch upstream repositories')


    args = parser.parse_args(argv)
    repo = config.repo
    is_mbox = config.mode == Config.Mode.MBOX

    if is_mbox:
        repo.register_mbox(config)

    # Update upstream
    if not args.noup:
        if not args.nofetch:
            log.info('Fetching and syncing upstream repository')
            repo.update()
        config.load_upstream_hashes(force_reload=True)

        if is_mbox and args.mbox:
            repo.update_mbox(config, nofetch=args.nofetch)

    if args.clear is None and args.create is None:
        args.create = 'all'

    create_stack, create_upstream, create_mbox = parse_choices(config, args.create)
    clear_stack, clear_upstream, clear_mbox = parse_choices(config, args.clear)

    if clear_stack:
        remove_if_exist(config.f_ccache_stack)
    if clear_upstream:
        remove_if_exist(config.f_ccache_upstream)
    if clear_mbox:
        remove_if_exist(config.f_ccache_mbox)
        remove_if_exist(config.f_mail_thread_cache)

    if create_stack:
        config.update_ccache_stack()
    if create_upstream:
        config.update_ccache_upstream()
    if create_mbox:
        config.update_ccache_mbox()

        # Update the mail thread cache
        repo.mbox.load_threads()
        repo.mbox.threads.update()
