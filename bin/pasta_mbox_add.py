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
    parser.add_argument('-maildir', dest='maildir', action='store_true',
                        default=False,
                        help='filename is a maildir, not a mailbox')

    args = parser.parse_args(argv)
    filename = os.path.realpath(args.filename)
    listname = args.listname

    if args.maildir:
        processor = './process_maildir.sh'
        if not os.path.isdir(filename):
            log.error('not a direcotry: %s' % filename)
            quit(-1)
    else:
        processor = './process_mailbox.sh'
        if not os.path.isfile(filename):
            log.error('does not exist: %s' % filename)
            quit(-1)

    log.info('Processing Mailbox')
    cwd = os.getcwd()
    os.chdir(os.path.join(cwd, 'tools'))
    ret = call([processor, listname, filename, config.d_mbox])
    os.chdir(cwd)
    if ret == 0:
        log.info('  ↪ done')
    else:
        log.error('Mail processor failed!')


if __name__ == '__main__':
    config = Config(sys.argv[1])
    mbox_add(config, sys.argv[0], sys.argv[2:])
