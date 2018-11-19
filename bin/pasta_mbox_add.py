#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2017-2018

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


def mbox_add(config):
    mail_processor(config, config.mbox_raw, 'Processing raw mailing list',
                   './process_mailbox_maildir.sh')

    mail_processor(config, config.mbox_git_public_inbox,
                   'Processing GIT public inbox',
                   './process_git_public_inbox.sh')


if __name__ == '__main__':
    config = Config(sys.argv[1])
    mbox_add(config)
