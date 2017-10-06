#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import os
import sys

from subprocess import call

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))
from PaStA import *


def mbox_prepare(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Prepare mailbox')

    parser.add_argument('listname', metavar='listname', type=str,
                        help='List name')
    parser.add_argument('filename', metavar='filename', type=str,
                        help='Mailbox filename')

    args = parser.parse_args(argv)
    filename = os.path.realpath(args.filename)
    listname = args.listname

    # check if mailbox is already prepared
    if not os.path.isfile(filename):
        print('Error: \'%s\' does not exist' % filename)
        quit(-1)

    printn('Processing Mailbox...')
    cwd = os.getcwd()
    os.chdir(os.path.join(cwd, 'tools'))
    call(['./process_mailbox.sh', listname, filename, config.d_mbox])
    os.chdir(cwd)
    done()


if __name__ == '__main__':
    config = Config(sys.argv[1])
    mbox_prepare(config, sys.argv[0], sys.argv[2:])
