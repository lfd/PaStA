"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2020

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import email
import glob
import hashlib
import os
import pygit2
import re
import requests

from datetime import datetime
from email.charset import CHARSETS
from logging import getLogger
from subprocess import Popen
from urllib.parse import urljoin

from .MailThread import MailThread
from .MessageDiff import MessageDiff, Signature
from ..Util import get_commit_hash_range, mail_parse_date

log = getLogger(__name__[-15:])

PATCH_SUBJECT_REGEX = re.compile(r'\[.*?\]:? ?(.*)')
DIFF_START_REGEX = re.compile(r'^--- \S+/.+$')
ANNOTATION_REGEX = re.compile(r'^---\s*$')


def decode_payload(message):
    payload = message.get_payload(decode=True)
    if not payload:
        return None

    charset = message.get_content_charset()
    if charset not in CHARSETS:
        charset = 'ascii'

    payload = payload.decode(charset, errors='ignore')
    return payload


class PatchMail(MessageDiff):
    @staticmethod
    def extract_patch_mail(mail):
        id = mail['message-id']

        # The easy case: Mail is a raw text mail, and contains the patch inline
        payload = decode_payload(mail)
        if payload:
            return mail, payload

        # The complex case: mail consists of multiple parts:
        payload = mail.get_payload()
        if isinstance(payload, str):
            return mail, payload

        if not isinstance(payload, list):
            log.warning('IMPLEMENT ME! %s' % id)
            raise NotImplementedError('impl me')

        # Try to decode all message parts
        payload = [decode_payload(x) for x in payload]
        payload = list(filter(None, payload))
        # Let's test if one of the payloads can be converted to a
        # mail object. In that case, it's very likely that a patch created by
        # git format-patch was sent as attachment
        for p in payload:
            try:
                m = email.message_from_string(p)
                if len(m.defects) or len(m.keys()) == 0:
                    continue

                # Hey, we have a valid email as attachment. Use it.
                p = decode_payload(m)
                return m, p
            except:
                pass

        if len(payload) >= 2 and \
           isinstance(payload[0], str) and isinstance(payload[1], str) and \
           True in ['diff --' in x for x in payload]:
            return mail, payload[0] + payload[1]

        for p in payload:
            if 'From: ' in p or 'diff --' in p:
                return mail, p

        raise ValueError('Unable to find suitable payload')

    def __init__(self, mail, identifier):
        # Get informations on the author
        date = mail_parse_date(mail['Date'], assume_epoch=True)

        mail, payload = self.extract_patch_mail(mail)
        self.mail_subject = mail['Subject']

        author = str(mail['From'])
        author_name, author_email = email.utils.parseaddr(author)
        author = Signature(author_name, author_email, date)

        retval = parse_single_message(payload)
        if retval is None:
            raise TypeError('Unable to split mail to msg and diff')

        msg, annotation, diff = retval

        # reconstruct commit message
        subject = self.mail_subject
        match = PATCH_SUBJECT_REGEX.match(self.mail_subject)
        if match:
            subject = match.group(1)
        msg = [subject, ''] + msg

        content = msg, annotation, diff

        super(PatchMail, self).__init__(identifier, content, author)

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


def load_file(filename, must_exist=True):
    if not os.path.isfile(filename) and must_exist is False:
        return []

    with open(filename) as f:
        f = f.read().split('\n')

    while len(f) and not f[-1]:
        f.pop()

    f = [tuple(x.split(' ')) for x in f]

    return f


def process_mailbox_maildir(f_mbox_raw, name, d_mbox, mode):
    """
    :param f_mbox_raw: filename of the mbox/maildir
    :param name: index name
    :param d_mbox: destination directory
    :param mode: can either be 'raw', or 'patchwork'
    """
    if not os.path.exists(f_mbox_raw):
        log.error('no such file or directory: %s' % f_mbox_raw)
        quit(-1)

    p = Popen(['./process_mailbox_maildir.sh', mode, name, d_mbox, f_mbox_raw],
              cwd=os.path.join(os.getcwd(), 'tools'))
    if p.wait():
        log.error('Mail processor failed!')
        quit(-1)
    log.info('  ↪ done')


class MailContainer:
    @staticmethod
    def load_index(f_index):
        index = dict()
        entries = load_file(f_index, must_exist=False)

        for entry in entries:
            date, message_id, location = entry[0:3]
            patchwork_id = tuple(int(x) for x in entry[3:])
            dtime = datetime.strptime(date, '%Y/%m/%d')

            if message_id not in index:
                index[message_id] = list()

            index[message_id].append((dtime, date, location) + patchwork_id)

        return index

    def write_index(self, f_index):
        index = list()
        for message_id, candidates in self.index.items():
            for entry in candidates:
                format_date = entry[1]
                line = '%s %s ' % (format_date, message_id)
                # Append the location, and the optional patchwork-id
                line += ' '.join([str(x) for x in entry[2:]])
                index.append(line)
        index.sort()

        d_index = os.path.dirname(f_index)
        os.makedirs(d_index, exist_ok=True)
        with open(f_index, 'w') as f:
            f.write('\n'.join(index) + '\n')

    def get_ids(self, time_window=None):
        if time_window:
            return {x[0] for x in self.index.items() if
                    any(map(
                        lambda date: time_window[0] <= date <= time_window[1],
                        [y[0] for y in x[1]]))}

        return set(self.index.keys())

    def __contains__(self, message_id):
        return message_id in self.index


class PubInbox(MailContainer):
    MESSAGE_ID_REGEX = re.compile(r'.*(<.*>).*')

    def __init__(self, listaddr, shard, d_repo, f_index):
        self.listaddr = listaddr
        self.f_index = f_index
        self.d_repo = d_repo

        self.repo = pygit2.Repository(d_repo)
        self.index = self.load_index(self.f_index)

        log.info('  ↪ loaded mail index for %s (shard %u): found %d mails' %
                 (listaddr, shard, len(self.index)))

    def get_blob(self, commit):
        if 'm' not in self.repo[commit].tree:
            return None

        blob = self.repo[commit].tree['m'].hex
        return self.repo[blob].data

    def get_mail_by_commit(self, commit):
        blob = self.get_blob(commit)
        if not blob:
            return None

        return email.message_from_bytes(blob)

    def get_mails_by_message_id(self, message_id):
        commits = self.get_hashes(message_id)
        return [self.get_mail_by_commit(commit) for commit in commits]

    def get_hashes(self, message_id):
        return [x[2] for x in self.index[message_id]]

    def __getitem__(self, message_id):
        commits = self.get_hashes(message_id)
        return [self.get_blob(commit) for commit in commits]

    def update(self):
        log.info('Update list %s' % self.listaddr)
        self.repo = pygit2.Repository(self.d_repo)

        known_hashes = set()
        for entry in self.index.values():
            known_hashes |= {x[2] for x in entry}

        hashes = set(get_commit_hash_range(self.d_repo, 'HEAD'))

        hashes = hashes - known_hashes
        log.info('Updating %d emails' % len(hashes))

        for hash in hashes:
            mail = self.get_mail_by_commit(hash)
            if not mail:
                log.warning('No email behind commit %s' % hash)
                continue

            # There are broken mails that may contain multiple Message-IDs.
            # Hence, get all Message-IDs and search for the sanest one
            ids = mail.get_all('Message-Id')
            if ids is None or len(ids) == 0:
                log.warning('No Message-Id in commit %s' % hash)
                continue

            id = max(ids, key=len)
            id = ''.join(id.split())
            # Try to do repair some broken message IDs. This only makes
            # sense if the message ids have a 'sane' length
            if len(id) > 10 and id[0] != '<' and id[-1] != '>':
                id = '<%s>' % id
            match = PubInbox.MESSAGE_ID_REGEX.match(id)
            if match:
                id = match.group(1)
            else:
                log.warning('Unable to parse Message ID: %s' % id)
                continue

            date = mail_parse_date(mail['Date'])
            if not date:
                log.warning('Unable to parse datetime %s of %s (%s)' %
                            (mail['Date'], id, hash))
                continue

            format_date = date.strftime('%04Y/%m/%d')

            if id not in self.index:
                self.index[id] = list()
            self.index[id].append((date, format_date, hash))

        self.write_index(self.f_index)


class MboxRaw(MailContainer):
    def __init__(self, d_mbox, d_index):
        self.d_mbox = d_mbox
        self.d_mbox_raw = os.path.join(d_mbox, 'raw')
        self.d_index = d_index
        self.index = {}
        self.raw_mboxes = []

    def add_mbox(self, listname, f_mbox_raw):
        self.raw_mboxes.append((listname, f_mbox_raw))
        f_mbox_index = os.path.join(self.d_index, 'raw.%s' % listname)
        index = self.load_index(f_mbox_index)
        log.info('  ↪ loaded mail index for %s: found %d mails' % (listname, len(index)))

        for id, desc in index.items():
            if id in self.index:
                self.index[id] += desc
            else:
                self.index[id] = desc

        return set(index.keys())

    def update(self):
        for listname, f_mbox_raw in self.raw_mboxes:
            log.info('Processing raw mailbox %s' % listname)
            process_mailbox_maildir(f_mbox_raw, listname, self.d_mbox, 'raw')

    def __getitem__(self, message_id):
        ret = list()

        for _, date_str, md5 in self.index[message_id]:
            filename = os.path.join(self.d_mbox_raw, date_str, md5)
            with open(filename, 'rb') as f:
                ret.append(f.read())

        return ret


class PatchworkProject(MailContainer):
    NEXT_PAGE_REGEX = re.compile('.*[&?]page=(\d+).*')

    def __init__(self, url, project_id, page_size, d_mbox, f_index, f_mbox_raw):
        self.url = url
        self.page_size = page_size
        self.project_id = project_id
        self.f_index = f_index
        self.f_mbox_raw = f_mbox_raw
        self.d_mbox = d_mbox
        self.d_mbox_patchwork = os.path.join(self.d_mbox, 'patchwork')
        self.index = self.load_index(self.f_index)
        log.info('  ↪ loaded mail index for Patchwork project id %u: found %d mails' %
                 (project_id, len(self.index)))


    def _get_page(self, page):
        params = dict()
        params['order'] = 'id'
        params['project'] = self.project_id
        params['per_page'] = self.page_size
        params['page'] = page

        resp = requests.get(urljoin(self.url, 'patches'), params)
        resp.raise_for_status()
        json = resp.json()

        page = {int(entry['id']):
                    (datetime.fromisoformat(entry['date']),
                     entry['msgid'],
                     entry['mbox'])
                for entry in json}

        next_page = None
        if 'next' in resp.links and 'url' in resp.links['next']:
            next_url = resp.links['next']['url']
            match = self.NEXT_PAGE_REGEX.match(next_url)
            if match:
                next_page = int(match.group(1))

        return next_page, page

    @staticmethod
    def _pull_patch(url):
        resp = requests.get(url)
        resp.raise_for_status()
        md5sum = hashlib.md5(resp.content).hexdigest()
        return md5sum, resp.content

    def update(self):
        if self.f_mbox_raw:
            log.info('Processing raw mailbox for Patchwork project id %u' %
                     self.project_id)
            process_mailbox_maildir(self.f_mbox_raw, str(self.project_id),
                           self.d_mbox, mode='patchwork')
            log.info('  ↪ Initial import successful. You can now remove the initial_archive in the configuration')
            return

        # Get a set of all present patchwork-ids
        patchwork_ids = set() \
            .union(*[{entry[3] for entry in idx_entry}
                     for idx_entry in self.index.values()])
        next_page = len(patchwork_ids)//self.page_size + 1
        pulled = 0

        try:
            while next_page:
                log.info('Querying page %u' % next_page)
                next_page, page = self._get_page(next_page)

                missing_ids = page.keys() - patchwork_ids
                for missing_id in sorted(missing_ids):
                    log.info(' Receiving patch %u' % missing_id)
                    date, message_id, url = page[missing_id]
                    format_date = date.strftime('%04Y/%m/%d')

                    # Download the raw, unencoded patch
                    md5sum, patch = self._pull_patch(url)

                    # Persist it
                    d_patch = os.path.join(self.d_mbox_patchwork, format_date)
                    f_patch = os.path.join(d_patch, md5sum)
                    os.makedirs(d_patch, exist_ok=True)
                    if not os.path.exists(f_patch):
                        with open(f_patch, 'wb') as f:
                            f.write(patch)

                    # Index it
                    if message_id not in self.index:
                        self.index[message_id] = list()
                    self.index[message_id].append((date, format_date, md5sum, missing_id))
                    pulled += 1
        except Exception as e:
            log.error(' An error occurred while fetching patches from Patchwork: %s' % str(e))

        log.info('  ↪ Pulled %u patches in total' % pulled)
        if pulled:
            self.write_index(self.f_index)

    def __getitem__(self, message_id):
        ret = list()

        for _, date_str, md5, _ in self.index[message_id]:
            filename = os.path.join(self.d_mbox_patchwork, date_str, md5)
            with open(filename, 'rb') as f:
                ret.append(f.read())

        return ret

    def get_patchwork_id(self, message_id):
        return self.index[message_id][0][3]


class Mbox:
    def __init__(self, config):
        self.threads = None
        self.f_mail_thread_cache = config.f_mail_thread_cache
        self.message_id_to_lists = dict()
        self.lists = set()
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

        # If Patchwork projects are defined in the config, no need to load raw mboxes and pubins.
        self.patchwork_projects = []
        if len(config.patchwork['projects']):
            log.info('Loading Patchwork projects...')
        for project_id, f_mbox_raw, listaddr in config.patchwork['projects']:
            self.lists.add(listaddr)
            f_index = os.path.join(
                config.d_mbox, 'index', 'patchwork.%u' % project_id)
            project = PatchworkProject(config.patchwork['url'], project_id,
                                       config.patchwork['page_size'],
                                       self.d_mbox, f_index, f_mbox_raw)
            for message_id in project.get_ids():
                self.add_mail_to_list(message_id, listaddr)
            self.patchwork_projects.append(project)

        if len(config.mbox_raw):
            log.info('Loading raw mailboxes...')
        self.mbox_raw = MboxRaw(self.d_mbox, self.d_index)
        for host, listname, f_mbox_raw in config.mbox_raw:
            listaddr = '%s@%s' % (listname, host)
            self.lists.add(listaddr)
            ids = self.mbox_raw.add_mbox(listaddr, f_mbox_raw)
            for message_id in ids:
                self.add_mail_to_list(message_id, listaddr)

        self.pub_in = []
        if len(config.mbox_git_public_inbox):
            log.info('Loading public inboxes')
        for host, mailinglists in config.mbox_git_public_inbox:
            for mailinglist in mailinglists:
                listaddr = '%s@%s' % (mailinglist, host)
                self.lists.add(listaddr)

                shard = 0
                while True:
                    d_repo = os.path.join(config.d_mbox, 'pubin', host,
                                          mailinglist, '%u.git' % shard)
                    f_index = os.path.join(config.d_mbox, 'index', 'pubin',
                                           host, mailinglist, '%u' % shard)

                    if os.path.isdir(d_repo):
                        inbox = PubInbox(listaddr, shard, d_repo, f_index)
                        for message_id in inbox.get_ids():
                            self.add_mail_to_list(message_id, listaddr)
                        self.pub_in.append(inbox)
                    else:
                        if shard == 0:
                            log.error('Unable to find shard 0 of list %s' %
                                      listname)
                            quit()
                        break

                    shard += 1

    def load_threads(self):
        if not self.threads:
            self.threads = MailThread.load(self.f_mail_thread_cache, self)
        return self.threads

    def add_mail_to_list(self, message_id, list):
        if message_id not in self.message_id_to_lists:
            self.message_id_to_lists[message_id] = set()
        self.message_id_to_lists[message_id].add(list)

    def __contains__(self, message_id):
        for public_inbox in self.pub_in:
            if message_id in public_inbox:
                return True

        if message_id in self.mbox_raw:
            return True

        for project in self.patchwork_projects:
            if message_id in project:
                return True

        return False

    def __getitem__(self, message_id):
        messages = self.get_messages(message_id)
        exception = None

        if len(messages) == 0:
            raise KeyError('Message not found')

        for message in messages:
            try:
                patch = PatchMail(message, message_id)
                return patch
            except Exception as e:
                exception = e

        raise exception

    def get_messages(self, id):
        raws = self.get_raws(id)

        return [email.message_from_bytes(raw) for raw in raws]

    def get_raws(self, message_id):
        raws = list()

        for project in self.patchwork_projects:
            if message_id in project:
                raws += project[message_id]

        for public_inbox in self.pub_in:
            if message_id in public_inbox:
                raws += public_inbox[message_id]

        if message_id in self.mbox_raw:
            raws += self.mbox_raw[message_id]

        return raws

    def get_ids(self, time_window=None, allow_invalid=False, lists=None):
        ids = set()

        for project in self.patchwork_projects:
            ids |= project.get_ids(time_window)

        for pub in self.pub_in:
            ids |= pub.get_ids(time_window)

        ids |= self.mbox_raw.get_ids(time_window)

        if not allow_invalid:
            ids = ids - self.invalid

        if lists:
            ids = {id for id in ids if len(self.get_lists(id) & lists)}

        return ids

    def update(self):
        for project in self.patchwork_projects:
            project.update()

        self.mbox_raw.update()

        for pub in self.pub_in:
            pub.update()

    def get_lists(self, message_id):
        return self.message_id_to_lists[message_id]

    def get_patchwork_ids(self, message_id):
        ret = list()
        for project in self.patchwork_projects:
            if message_id in project:
                ret.append(project.get_patchwork_id(message_id))
        return ret

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
