#!/usr/bin/env python3

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
from subprocess import call

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


def mail_processor(config, iter, message, processor):
    for listname, target in iter:
        if not os.path.exists(target):
            log.error('not a file or directory: %s' % target)
            quit(-1)

        log.info(message + ' %s' % listname)
        cwd = os.getcwd()
        os.chdir(os.path.join(cwd, 'tools'))
        ret = call([processor, listname, target, config.d_mbox])
        os.chdir(cwd)
        if ret == 0:
            log.info('  ↪ done')
        else:
            log.error('Mail processor failed!')


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

    args = parser.parse_args(argv)
    repo = config.repo

    # Update upstream
    log.info('Fetching and syncing upstream repository')
    repo.repo.remotes['origin'].fetch()
    config.load_upstream_hashes(force_reload=True)

    if args.mbox and config.mode == Config.Mode.MBOX:
        mail_processor(config, config.mbox_raw, 'Processing raw mailing list',
                       './process_mailbox_maildir.sh')

        mail_processor(config, config.mbox_git_public_inbox,
                       'Processing GIT public inbox',
                       './process_git_public_inbox.sh')

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
    sync(config, sys.argv[0], sys.argv[2:])
