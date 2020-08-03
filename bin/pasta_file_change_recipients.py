"""
PaStA - Patch Stack Analysis

Author:
  Shubhamkumar Pandey <b18194@students.iitmandi.ac.in>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import os
import sys
import argparse
import pickle

from tqdm import tqdm
from os.path import join, exists
from collections import defaultdict, Counter
from logging import getLogger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *
from pypasta.LinuxMailCharacteristics import email_get_recipients
from pypasta.Repository.Patch import Diff

log = getLogger(__name__[-15:])


def dump_pkl(config : Config, f_recipients_pkl : str = None):
    repo = config.repo
    RECIPIENTS = defaultdict(Counter)
    for message_id in tqdm(repo.mbox.get_ids(time_window=config.mbox_time_window)):
        patch = repo[message_id]
        mail = repo.mbox.get_messages(message_id)[0]
        recipients = email_get_recipients(mail)
        for filename in patch.diff.affected:
            for recipient in recipients:
                RECIPIENTS[filename][recipient] += 1

    if f_recipients_pkl:
        pickle.dump(RECIPIENTS, open(f_recipients_pkl, 'wb'))

    return RECIPIENTS


def file_change_recipients(config : Config, argv : list):

    parser = argparse.ArgumentParser(prog='predict', description='Get recipients of the patch file passed \
                                    considering the files changed in the diff.')

    parser.add_argument('--gen', dest='_generate', action="store_true",
                        help='Generate file_change_recipient.pkl file as per current config')
    parser.add_argument('--patch', dest='f_patch', metavar='patch', default=None, type=str,
                        help='Path to the patch file')
    parser.add_argument('--out', dest='f_out', metavar='outpath', type=str, default=None,
                        help='Provide a path to output file containing the list of recipients related to \
                        the patch')

    args = parser.parse_args(argv)
    repo = config.repo
    repo.register_mbox(config)

    f_recipients_pkl = join(config._project_root, 'resources/file_change_recipients.pkl')

    if args._generate:
        log.info('Evaluating recipients relation with respect to files changed')
        if exists(f_recipients_pkl):
            os.remove(f_recipients_pkl)
        RECIPIENTS = dump_pkl(config, f_recipients_pkl)

    elif exists(f_recipients_pkl):
        RECIPIENTS = pickle.load(open(f_recipients_pkl, 'rb'))

    else:
        log.info('file_change_recipients.pkl was not found')
        RECIPIENTS = dump_pkl(config, f_recipients_pkl)

    if args.f_patch:
        args.f_patch = join(os.getcwd(),args.f_patch)
        diff = Diff(open(args.f_patch, 'r').readlines())

        recipients = set()
        for filename in diff.affected:
            if filename in RECIPIENTS:
                recipients |= set(RECIPIENTS[filename].keys())

        if not args.f_out:
            args.f_out = f'{args.f_patch}.recipients'

        args.f_out = os.path.join(os.getcwd(), args.f_out)

        with open(args.f_out, 'w') as f:
            f.write('\n'.join(recipients))

        log.info(f'The related recipient list for the patch is stored in {args.f_out}')
