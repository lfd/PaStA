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
import os
import quopri
import re

from email.charset import CHARSETS
from logging import getLogger

from .MessageDiff import MessageDiff

log = getLogger(__name__[-15:])

MAIL_FROM_REGEX = re.compile(r'(.*) <(.*)>')
PATCH_SUBJECT_REGEX = re.compile(r'\[.*\]:? ?(.*)')


class PatchMail(MessageDiff):
    def __init__(self, content):
        mail = email.message_from_bytes(content)

        # Simply name it commit_hash, otherwise we would have to refactor
        # tons of code.
        self.commit_hash = mail['Message-ID']
        self.mail_subject = mail['Subject']

        # we need timezone aware datetimes due to the fact, that most of all
        # emails contain timezone aware timestamps. There's an issue with
        # timezone unaware timestamps: they can't be compared to timezone aware
        # timestamps. To cope with that, we simple shift those mails to UTC
        # (which is also true in most cases).
        #
        # E.g. python converts this timestamp to an timezone unaware one,
        # while it is GMT:
        #   'Fri, 23 Feb 2007 13:35:50 -0000 (GMT)'
        try:
            date = email.utils.parsedate_to_datetime(mail['Date'])
        except:
            # assume epoch
            log.debug('  Message %s: unable to parse date %s' %
                      (self.commit_hash, mail['Date']))
            date = datetime.datetime.utcfromtimestamp(0)

        if date.tzinfo is None:
            date = date.replace(tzinfo=datetime.timezone.utc)

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
        msg, annotation, diff = parse_payload(payload)

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

        content = msg, annotation, diff

        super(PatchMail, self).__init__(content, author_name, author_email,
                                        date)

    def format_message(self):
        custom = ['Mail Subject: %s' % self.subject]
        return super(PatchMail, self).format_message(custom)


def parse_single_message(mail):
    # Before using splitlines(), we have to replace ASCII \f by sth. else, like
    # a whitespace. Otherwise weird things happen.
    mail = mail.replace('\f', ' ')

    mail = mail.splitlines()

    message = []
    patch = None
    annotation = None

    for line in mail:
        if patch is None and \
                (line.startswith('diff ') or line.startswith('--- a/')):
            patch = list()
        elif annotation is None and patch is None and line.startswith('---'):
            annotation = list()
            # Skip this line, we're not interested in the --- line.
            continue

        if patch is not None:
            patch.append(line)
        elif annotation is not None:
            annotation.append(line)
        else:
            message.append(line)

    if patch:
        return message, annotation, patch

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
    def strip_trailing_newlines(string):
        if string is not None and len(string) and string[-1] == '':
            string.pop()

    if isinstance(payload, list):
        retval = parse_list(payload)
    elif isinstance(payload, str):
        retval = parse_single_message(payload)
    else:
        raise TypeError('Warning: unknown payload type')

    if retval is None:
        raise TypeError('Unable to split mail to msg and diff')

    msg, annotation, diff = retval

    # Remove last line of message if empty
    strip_trailing_newlines(msg)
    strip_trailing_newlines(annotation)

    return msg, annotation, diff


class Mbox:
    def __init__(self, d_mbox):
        self.d_mbox = d_mbox
        self.f_mbox_lists = os.path.join(d_mbox, 'lists')
        self.f_mbox_index = os.path.join(d_mbox, 'index')
        self.f_mbox_invalid = os.path.join(d_mbox, 'invalid')

        log.info('Loading Mailbox')
        lists = dict()
        for message_id, list_name in Mbox._load_file(self.f_mbox_lists):
            if message_id not in lists:
                lists[message_id] = set()
            lists[message_id].add(list_name)
        log.info('  ↪ loaded mail-to-list mappings: %s mappings' % len(lists))

        self.index = Mbox._load_index(self.f_mbox_index, lists)
        log.info('  ↪ loaded mail index: found %d mails', len(self.index))
        self.invalid = Mbox._load_index(self.f_mbox_invalid, lists, False)
        log.info('  ↪ loaded invalid mail index: found %d invalid mails'
                 % len(self.invalid))

    @staticmethod
    def _load_index(filename, lists, must_exist=True):
        content = Mbox._load_file(filename, must_exist)
        return {x[1]: (datetime.datetime.strptime(x[0], "%Y/%m/%d"),
                       x[0], x[2], lists[x[1]]) for x in content}

    @staticmethod
    def _load_file(filename, must_exist=True):
        if not os.path.isfile(filename) and must_exist is False:
            return []

        with open(filename) as f:
            f = f.read().split('\n')
            # last element is empty
            f.pop()
        f = [tuple(x.split(' ')) for x in f]

        return f

    def __getitem__(self, message_id):
        _, date_str, md5, _ = self.index[message_id]
        filename = os.path.join(self.d_mbox, date_str, md5)
        with open(filename, 'rb') as f:
            return PatchMail(f.read())

    def __contains__(self, item):
        return item in self.index

    def message_ids(self, time_window=None):
        if time_window:
            return [x[0] for x in self.index.items()
                    if time_window[0] <= x[1][0] <= time_window[1]]
        else:
            return self.index.keys()

    def get_lists(self, message_id):
        return self.index[message_id][3]

    def invalidate(self, invalid):
        def write_index(filename, foo):
            with open(filename, 'w') as f:
                ret = ['%s %s %s' % (x[1][1], x[0], x[1][2]) for x in foo]
                ret = '\n'.join(ret) + '\n'
                f.write(ret)

        for message_id in invalid:
            self.invalid[message_id] = self.index.pop(message_id)

        invalid = sorted(self.invalid.items())
        valid = sorted(self.index.items())

        if len(valid):
            write_index(self.f_mbox_index, valid)
        if len(invalid):
            write_index(self.f_mbox_invalid, invalid)
