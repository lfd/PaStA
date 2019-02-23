"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import datetime
import dateparser
import email
import git
import glob
import os
import pygit2
import quopri
import re

from email.charset import CHARSETS
from logging import getLogger
from subprocess import call

from .MailThread import MailThread
from .MessageDiff import MessageDiff
from ..Util import get_commit_hash_range

log = getLogger(__name__[-15:])

MAIL_FROM_REGEX = re.compile(r'(.*) <(.*)>')
PATCH_SUBJECT_REGEX = re.compile(r'\[.*\]:? ?(.*)')
DIFF_START_REGEX = re.compile(r'^--- \S+/.+$')
ANNOTATION_REGEX = re.compile(r'^---\s*$')


def mail_parse_date(date_str):
    try:
        date = email.utils.parsedate_to_datetime(date_str)
    except Exception:
        date = None
    if not date:
        try:
            date = dateparser.parse(date_str)
        except Exception:
            date = None
    return date


class PatchMail(MessageDiff):
    def __init__(self, mail):
        # Simply name it commit_hash, otherwise we would have to refactor
        # tons of code.
        self.commit_hash = mail['Message-ID']
        self.mail_subject = mail['Subject']

        date = mail_parse_date(mail['Date'])
        if not date:
            # assume epoch
            log.debug('  Message %s: unable to parse date %s' %
                      (self.commit_hash, mail['Date']))
            date = datetime.datetime.utcfromtimestamp(0)

        if date.tzinfo is None:
            date = date.replace(tzinfo=datetime.timezone.utc)

        payload = mail.get_payload(decode=True)
        charset = mail.get_content_charset()

        if charset not in CHARSETS:
           charset = 'ascii'
        payload = payload.decode(charset, errors='ignore')

        if isinstance(payload, list):
            retval = parse_list(payload)
        elif isinstance(payload, str):
            retval = parse_single_message(payload)
        else:
            raise TypeError('Warning: unknown payload type')

        if retval is None:
            raise TypeError('Unable to split mail to msg and diff')

        msg, annotation, diff = retval

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

    if mail[0].startswith('--'):
        mail.pop(0)

    for line in mail:
        if patch is None and \
                (line.startswith('diff ') or
                 DIFF_START_REGEX.match(line) or
                 line.lower().startswith('index: ')):
            patch = list()
        elif annotation is None and patch is None \
             and ANNOTATION_REGEX.match(line):
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


def load_file(filename, must_exist=True):
    if not os.path.isfile(filename) and must_exist is False:
        return []

    with open(filename) as f:
        f = f.read().split('\n')

    while len(f) and not f[-1]:
        f.pop()

    f = [tuple(x.split(' ')) for x in f]

    return f


def load_index(basename):
    result = load_file(basename, must_exist=False)
    for f_index in glob.glob(basename + '.*'):
        result += load_file(f_index)

    return {message_id: (datetime.datetime.strptime(date, "%Y/%m/%d"), date,
                         location)
            for (date, message_id, location) in result}


class MailContainer:
    def message_ids(self, time_window=None):
        if time_window:
            return {x[0] for x in self.index.items()
                    if time_window[0] <= x[1][0] <= time_window[1]}

        return set(self.index.keys())

    def __contains__(self, message_id):
        return message_id in self.index


class PubInbox(MailContainer):
    MESSAGE_ID_REGEX = re.compile(r'.*(<.*>).*')

    def __init__(self, d_index, d_repo, listname):
        self.d_repo = d_repo

        inbox_name = os.path.basename(d_repo)
        f_index = os.path.join(d_index, 'pubin.%s' % inbox_name)
        self.f_index = f_index
        self.repo = pygit2.Repository(d_repo)
        self.index = load_index(self.f_index)

        log.info('  ↪ loaded mail index for %s from %s: found %d mails' %
                 (listname, inbox_name, len(self.index)))

    def get_blob(self, commit):
        blob = self.repo[commit].tree['m'].hex
        return self.repo[blob].data

    def get_mail_by_commit(self, commit):
        return email.message_from_bytes(self.get_blob(commit))

    def get_mail_by_message_id(self, message_id):
        commit = self.get_hash(message_id)
        return self.get_mail_by_commit(commit)

    def get_hash(self, message_id):
        return self.index[message_id][2]

    def __getitem__(self, message_id):
        commit = self.get_hash(message_id)
        return self.get_blob(commit)

    def update(self):
        repo = git.Repo(self.d_repo)
        for remote in repo.remotes:
            remote.fetch()
        self.repo = pygit2.Repository(self.d_repo)

        known_hashes = {hash for (_, _, hash) in self.index.values()}
        hashes = set(get_commit_hash_range(self.d_repo, 'origin/master'))

        hashes = hashes - known_hashes
        log.info('Updating %d emails' % len(hashes))

        for hash in hashes:
            mail = self.get_mail_by_commit(hash)
            if not mail['Message-ID']:
                log.warning('No Message ID in commit %s' % hash)
                continue
            message_id = mail['Message-ID'].replace(' ', '').strip()
            match = PubInbox.MESSAGE_ID_REGEX.match(message_id)
            if not match:
                log.warning('Unable to parse Message ID: %s' % message_id)
                continue

            message_id = match.group(1)

            if message_id in self.index:
                log.warning('Duplicate Message id %s. Skipping' % message_id)
                continue

            date = mail_parse_date(mail['Date'])
            if not date:
                log.warning('Unable to parse datetime %s of %s (%s)' %
                            (mail['Date'], message_id, hash))
                continue

            format_date = date.strftime('%04Y/%m/%d')

            self.index[message_id] = date, format_date, hash

        with open(self.f_index, 'w') as f:
            index = ['%s %s %s' % (format_date, message_id, commit)
                     for (message_id, (date, format_date, commit))
                     in self.index.items()]
            index.sort()
            f.write('\n'.join(index) + '\n')


class MboxRaw(MailContainer):
    def __init__(self, d_mbox, d_index):
        self.d_mbox = d_mbox
        self.d_mbox_raw = os.path.join(d_mbox, 'raw')
        self.d_index = d_index
        self.index = {}
        self.lists = {}
        self.raw_mboxes = []

    def add_mbox(self, listname, f_mbox_raw):
        self.raw_mboxes.append((listname, f_mbox_raw))
        f_mbox_index = os.path.join(self.d_index, 'raw.%s' % listname)
        index = load_index(f_mbox_index)
        log.info('  ↪ loaded mail index for %s: found %d mails' % (listname, len(index)))
        self.index = {**self.index, **index}
        return set(index.keys())

    def update(self):
        for listname, f_mbox_raw in self.raw_mboxes:
            if not os.path.exists(f_mbox_raw):
                log.error('not a file or directory: %s' % f_mbox_raw)
                quit(-1)

            log.info('Processing raw mailbox %s' % listname)
            cwd = os.getcwd()
            os.chdir(os.path.join(cwd, 'tools'))
            ret = call(['./process_mailbox_maildir.sh', listname, self.d_mbox, f_mbox_raw])
            os.chdir(cwd)
            if ret == 0:
                log.info('  ↪ done')
            else:
                log.error('Mail processor failed!')

    def __getitem__(self, message_id):
        _, date_str, md5 = self.index[message_id]
        filename = os.path.join(self.d_mbox_raw, date_str, md5)
        with open(filename, 'rb') as f:
            return f.read()


class Mbox:
    def __init__(self, config):
        self.threads = None
        self.f_mail_thread_cache = config.f_mail_thread_cache
        self.lists = dict()
        self.d_mbox = config.d_mbox
        self.d_invalid = os.path.join(self.d_mbox, 'invalid')
        self.d_index = os.path.join(self.d_mbox, 'index')

        log.info('Loading mailbox subsystem')

        os.makedirs(self.d_invalid, exist_ok=True)
        os.makedirs(self.d_index, exist_ok=True)

        self.invalid = set()
        for f_inval in glob.glob(os.path.join(self.d_invalid, '*')):
            self.invalid |= {x[0] for x in load_file(f_inval)}
        log.info('  ↪ loaded invalid mail index: found %d invalid mails'
                 % len(self.invalid))

        if len(config.mbox_raw):
            log.info('Loading raw mailboxes...')
        self.mbox_raw = MboxRaw(self.d_mbox, self.d_index)
        for listname, f_mbox_raw in config.mbox_raw:
            message_ids = self.mbox_raw.add_mbox(listname, f_mbox_raw)
            for message_id in message_ids:
                self.add_mail_to_list(message_id, listname)

        self.pub_in = []
        self.pub_in_index = dict()
        if len(config.mbox_git_public_inbox):
            log.info('Loading public inboxes')
        for listname, d_repo in config.mbox_git_public_inbox:
            if not os.path.isabs(d_repo):
                d_repo = os.path.join(config.d_mbox, 'pubin', d_repo)

            idx = len(self.pub_in)
            inbox = PubInbox(self.d_index, d_repo, listname)
            for message_id in inbox.message_ids():
                self.pub_in_index[message_id] = idx
                self.add_mail_to_list(message_id, listname)

            self.pub_in.append(inbox)

    def load_threads(self):
        if not self.threads:
            self.threads = MailThread.load(self.f_mail_thread_cache, self)
        return self.threads

    def add_mail_to_list(self, message_id, list):
        if message_id not in self.lists:
            self.lists[message_id] = set()
        self.lists[message_id].add(list)

    def __contains__(self, message_id):
        if message_id in self.pub_in_index:
            return True

        if message_id in self.mbox_raw:
            return True

        return False

    def __getitem__(self, message_id):
        message = self.get_message(message_id)
        return PatchMail(message)

    def get_message(self, message_id):
        raw = self.get_raw(message_id)
        if raw is None:
            return None

        return email.message_from_bytes(raw)

    def get_raw(self, message_id):
        if message_id in self.pub_in_index:
            idx = self.pub_in_index[message_id]
            pub_in = self.pub_in[idx]
            return pub_in[message_id]

        if message_id in self.mbox_raw:
            return self.mbox_raw[message_id]

        return None

    def message_ids(self, time_window=None, allow_invalid=False):
        ids = set()

        for pub in self.pub_in:
            ids |= pub.message_ids(time_window)

        ids |= self.mbox_raw.message_ids(time_window)

        if allow_invalid:
            return ids

        return ids - self.invalid

    def update(self):
        self.mbox_raw.update()

        for pub in self.pub_in:
            pub.update()

    def get_lists(self, message_id):
        return self.lists[message_id]

    def invalidate(self, invalid):
        self.invalid |= set(invalid)

        # For data persistence, note that we have to split invalid list to
        # chunks of 1.000.000 entries (~50MiB) to overcome GitHub's maximum
        # file size.
        chunksize = 1000000

        invalid = list(self.invalid)
        invalid.sort()

        invalid = [invalid[x:x+chunksize]
                   for x in range(0, len(invalid), chunksize)]

        for no, inv in enumerate(invalid):
            f_invalid = os.path.join(self.d_invalid, '%d' % no)
            with open(f_invalid, 'w') as f:
                f.write('\n'.join(inv) + '\n')
