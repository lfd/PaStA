"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import datetime
import email
import functools
import mailbox
import quopri
import re
import sys
import time

from email.charset import CHARSETS
from multiprocessing import cpu_count, Pool
from termcolor import colored

from .Repository import Commit


MAIL_FROM_REGEX = re.compile(r'(.*) <(.*)>')
PATCH_SUBJECT_REGEX = re.compile(r'\[(.*)\]:? ?(.*)')


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
        print('Warning: unknown payload type')
        return None

    if retval is None:
        return None

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


def parse_mail(mindate, maxdate, mail):
    message_id = mail['Message-ID']

    try:
        date = time.mktime(email.utils.parsedate(mail['Date']))
    except:
        # assume epoch
        date = 0

    date = datetime.datetime.fromtimestamp(date)
    if date < mindate or date > maxdate:
        return None

    payload = mail.get_payload()

    # Check encoding and decode
    cte = mail['Content-Transfer-Encoding']
    if cte == 'QUOTED-PRINTABLE':
        charset = mail.get_content_charset()
        if charset not in CHARSETS:
            charset = 'ascii'
        payload = quopri.decodestring(payload)
        payload = payload.decode(charset, errors='ignore')

    try:
        retval = parse_payload(payload)
    except:
        print('Mail parser error on message: %s' % message_id)
        return None

    if retval is None:
        return None

    try:
        msg, diff = retval
        # Insert message subject

        note = None
        subject = mail['Subject']
        match = PATCH_SUBJECT_REGEX.match(subject)
        if match:
            note = match.group(1)
            subject = match.group(2)

        msg = [subject, ''] + msg
        match = MAIL_FROM_REGEX.match(mail['From'])
        if match:
            author = match.group(1)
            author_email = match.group(2)
        else:
            author = mail['From']
            author_email = ''

        commit = Commit(message_id, msg, diff,
                        author, author_email, date,
                        'NOT COMMITTED', 'NOT COMMITTED', datetime.datetime.fromtimestamp(0),
                        note)
    except:
        print('Diff parser error: %s' % message_id)
        return None

    return message_id, commit


def fix_encoding(string):
    return string.encode('utf-8').decode('ascii', 'ignore')


def load_and_cache_mbox(repo, mbox_filename, mindate, maxdate, parallelise=True):
    print('Notice: Skipping mails until %s' % mindate)
    sys.stdout.write('Loading mbox %s...' % mbox_filename)
    mbox = mailbox.mbox(mbox_filename, create=False)

    print(colored(' [done]', 'green'))
    print('Parsing %d Mails...' % len(mbox))

    parse_mail_partial = functools.partial(parse_mail, mindate, maxdate)

    if parallelise:
        p = Pool(cpu_count())
        result = p.map(parse_mail_partial, mbox)
        p.close()
        p.join()
    else:
        result = list(map(parse_mail_partial, mbox))

    # Save memory
    del mbox

    # Filter None values
    result = dict(filter(bool, result))

    print('Found %d patches on mailing list' % len(result))

    repo.inject_commits(result)
    return set(result.keys())
