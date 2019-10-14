"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2020

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import io
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
    log.info('Removing %s' % filename)
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
                             'Possibilities: downstream / upstream / all. '
                             'Default: upstream. If -mbox is specified: all')
    parser.add_argument('-clear', metavar='clear', default=None,
                        choices=choices,
                        help='Invalidates cache. Usage same as create')
    parser.add_argument('-mbox', action='store_true', default=False,
                        help='Load mailbox subsystem')
    parser.add_argument('-p', dest='patchwork',
                        action='store_true', default=False,
                        help='Pull patches from patchwork')
    parser.add_argument('-noup', action='store_true', default=False,
                        help='Don\'t synchronise internal index files. ')

    args = parser.parse_args(argv)
    repo = config.repo
    is_mbox = config.mode == Config.Mode.MBOX

    # Choose sane defaults
    if args.clear is None and args.create is None:
        args.create = 'upstream'
        if args.mbox and is_mbox:
            args.create = 'all'

    if is_mbox and (args.create in ['downstream', 'all'] or args.mbox):
        repo.register_mbox(config)

        if args.patchwork:
            repo.mbox.register_patchwork(config)

    # Update upstream & pull patches from patchwork
    if not args.noup:
        config.load_upstream_hashes(force_reload=True)
        if is_mbox and args.mbox:
            if args.patchwork:
                pull_patches(config)

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
        if not config.mbox_use_patchwork_id:
            repo.mbox.load_threads()
            repo.mbox.threads.update()


def pull_patches(config: Config):
    since = config.repo.mbox.latest_message_date()
    if since is None:
        log.info('Pulling all patches from patchwork')
    else:
        log.info('Pulling patches from patchwork created since %s', since)

    lists = {list_id: path for list_id, path in config.mbox_raw}
    index = config.repo.mbox.mbox_raw.index
    patchwork = config.repo.mbox.patchwork
    patches = patchwork.download_patches(since, lists, ignore=index)

    pulled = 0
    try:
        for event_date, list_id, msg_id, mbox in patches:
            if isinstance(lists[list_id], str):
                # replace file path string with (open) file object
                lists[list_id] = open(lists[list_id], 'a')

            if mbox[-1] != '\n':
                mbox += '\n'
            lists[list_id].write(mbox + '\n')
            pulled += 1
    finally:
        for item in lists:
            # only call close on items we opened before
            if isinstance(item, io.TextIOBase):
                item.close()

    log.info('  ↪ Pulled %d patches', pulled)
