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


def mbox_add(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Prepare mailbox')

    parser.add_argument('listname', metavar='listname', type=str,
                        help='List name')
    parser.add_argument('filename', metavar='filename', type=str,
                        help='Mailbox filename / Maildir directory')

    args = parser.parse_args(argv)
    filename = os.path.realpath(args.filename)
    listname = args.listname

    if not os.path.exists(filename):
        log.error('not a file or direcotry: %s' % filename)
        quit(-1)

    log.info('Processing Mailbox / Maildir')
    cwd = os.getcwd()
    os.chdir(os.path.join(cwd, 'tools'))
    ret = call(['./process_mailbox_maildir.sh', listname, filename, config.d_mbox])
    os.chdir(cwd)
    if ret == 0:
        log.info('  ↪ done')
    else:
        log.error('Mail processor failed!')


if __name__ == '__main__':
    config = Config(sys.argv[1])
    mbox_add(config, sys.argv[0], sys.argv[2:])
