"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import datetime
import email
import mailbox
import os
import quopri
import re

from email.charset import CHARSETS

from .MessageDiff import MessageDiff

MAIL_FROM_REGEX = re.compile(r'(.*) <(.*)>')
PATCH_SUBJECT_REGEX = re.compile(r'\[.*\]:? ?(.*)')


class PatchMail(MessageDiff):
    def __init__(self, filename):
        mail = mailbox.mbox(filename, create=False)[0]

        # Simply name it commit_hash, otherwise we would have to refactor
        # tons of code.
        self.commit_hash = mail['Message-ID']
        self.mail_subject = mail['Subject']

        try:
            date = email.utils.parsedate_to_datetime(mail['Date'])
        except:
            # assume epoch
            date = datetime.datetime.utcfromtimestamp(0)

        payload = mail.get_payload()

        # Check encoding and decode
        cte = mail['Content-Transfer-Encoding']
        if cte == 'QUOTED-PRINTABLE':
            charset = mail.get_content_charset()
            if charset not in CHARSETS:
                charset = 'ascii'
            payload = quopri.decodestring(payload)
            payload = payload.decode(charset, errors='ignore')

        # MAY RAISE AN ERROR, FORBID RETURN NULL
        msg, diff = parse_payload(payload)

        # reconstruct commit message
        subject = self.mail_subject
        match = PATCH_SUBJECT_REGEX.match(self.mail_subject)
        if match:
            subject = match.group(1)
        msg = [subject, ''] + msg

        author_name = mail['From']
        author_email = ''
        match = MAIL_FROM_REGEX.match(author_name)
        if match:
            author_name = match.group(1)
            author_email = match.group(2)

        super(PatchMail, self).__init__(msg, diff, author_name, author_email,
                                        date)

    def format_message(self):
        custom = ['Mail Subject: %s' % self.subject]
        return super(PatchMail, self).format_message(custom)


def parse_single_message(mail):
    mail = mail.splitlines()

    valid = False

    message = []
    patch = []

    for line in mail:
        if line.startswith('diff '):
            valid = True

        if valid:
            patch.append(line)
        else:
            message.append(line)

    if valid:
        return message, patch

    return None


def parse_list(payload):
    if len(payload) == 1:
        retval = parse_single_message(payload[0].get_payload())
        if retval:
            return retval
        else:
            return None
    payload0 = payload[0].get_payload()
    payload1 = payload[1].get_payload()

    if not (isinstance(payload0, str) and isinstance(payload1, str)):
        return None

    payload0 = payload0.splitlines()
    payload1 = payload1.splitlines()

    if any([x.startswith('diff ') for x in payload1]):
        return payload0, payload1

    return None


def parse_payload(payload):
    if isinstance(payload, list):
        retval = parse_list(payload)
    elif isinstance(payload, str):
        retval = parse_single_message(payload)
    else:
        raise TypeError('Warning: unknown payload type')

    if retval is None:
        raise TypeError('Unable to split mail to msg and diff')

    msg, diff = retval

    # Remove last line of message if empty
    while len(msg) and msg[-1] == '':
        msg.pop()

    # Strip Diffstats
    diffstat_start = None
    for index, line in enumerate(msg):
        if diffstat_start is None and line == '---':
            diffstat_start = index
        elif not (len(line) and line[0] == ' '):
                diffstat_start = None
    if diffstat_start:
        msg = msg[0:diffstat_start]

    return msg, diff


def mbox_load_index(d_mbox):
    f_mbox_lists = os.path.join(d_mbox, 'lists')
    f_mbox_index = os.path.join(d_mbox, 'index')

    def load_file(filename):
        with open(filename) as f:
            f = f.read().split('\n')
            # last element is empty
            f.pop()
        f = [tuple(x.split(' ')) for x in f]

        return f

    print('Loading index...')
    lists = dict()
    for message_id, list_name in load_file(f_mbox_lists):
        if message_id not in lists:
            lists[message_id] = set()
        lists[message_id].add(list_name)

    index = load_file(f_mbox_index)
    index = {x[1]: (datetime.datetime.strptime(x[0], "%Y/%m/%d"), x[0], x[2],
                    lists[x[1]]) for x in index}

    return index


def mbox_write_index(d_mbox, index):
    f_mbox_lists = os.path.join(d_mbox, 'lists')
    f_mbox_index = os.path.join(d_mbox, 'index')

    items = sorted(index.items())

    index = ['%s %s %s' % (x[1][1], x[0], x[1][2]) for x in items]
    index = '\n'.join(index) + '\n'

    with open(f_mbox_index, 'w') as f:
        f.write(index)

    with open(f_mbox_lists, 'w') as f:
        for message_id, (_, _, _, lists) in items:
            for list in sorted(lists):
                f.write('%s %s\n' % (message_id, list))
