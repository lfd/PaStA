"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import csv
import email
import re

from anytree import LevelOrderIter
from enum import Enum
from logging import getLogger
from multiprocessing import Pool, cpu_count

from .MAINTAINERS import load_maintainers
from .Util import get_first_upstream, load_pkl_and_update, mail_parse_date

log = getLogger(__name__[-15:])


VALID_EMAIL_REGEX = re.compile(r'.+@.+\..+')

_repo = None
_maintainers_version = None
_clustering = None
_characteristics_class = None


class PatchType(Enum):
    PATCH = 'patch' # A regular patch written by a human author
    BOT = 'bot'
    NEXT = 'linux-next'
    STABLE = 'stable-review'
    NOT_PROJECT = 'not-project'
    PROCESS = 'process'
    NOT_FIRST = 'not-first' # Mail contains a patch, but it's not the first patch in the thread
    OTHER = 'other'


def email_get_recipients(message):
    recipients = message.get_all('To', []) + message.get_all('Cc', [])
    recipients = list(filter(None, recipients))
    # get_all might return Header objects. Convert them all to strings.
    recipients = [str(x) for x in recipients]

    # Only accept valid email addresses
    recipients = {x[1].lower() for x in email.utils.getaddresses(recipients)
                  if VALID_EMAIL_REGEX.match(x[1])}

    return recipients


def email_get_header_normalised(message, header):
    header = str(message[header] or '').lower()
    header = header.replace('\n', '').replace('\t', ' ')

    return header


def email_get_from(message):
    mail_from = email_get_header_normalised(message, 'From')
    return email.utils.parseaddr(mail_from)


class MailCharacteristics:
    REGEX_COVER = re.compile('\[.*patch.*\s0+/.*\].*', re.IGNORECASE)
    REGEX_GREG_ADDED = re.compile('patch \".*\" added to .*')

    BOTS = {'tip-bot2@linutronix.de', 'tipbot@zytor.com',
            'noreply@ciplatform.org', 'patchwork@emeril.freedesktop.org'}
    POTENTIAL_BOTS = {'broonie@kernel.org', 'lkp@intel.com'}
    PROCESSES = ['linux-next', 'git pull', 'rfc']

    @staticmethod
    def dump_release_info(config):
        relevant_releases = [
            (tag, date.strftime('%Y-%m-%d')) for tag, date in config.repo.tags if
                config.mbox_mindate < date.replace(tzinfo=None) < config.mbox_maxdate and
                '-rc' not in tag
        ]
        with open(config.f_releases, 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=['release', 'date'])
            writer.writeheader()
            for release, date in relevant_releases:
                writer.writerow({'release': release,
                                 'date': date})

    def _has_foreign_response(self, repo):
        """
        This function will return True, if there's another author in this
        thread, other than the ORIGINAL author. (NOT the author of this
        email)
        """
        if len(self.thread.children) == 0:
            return False  # If there is no response the check is trivial

        for mail in list(LevelOrderIter(self.thread)):
            # Beware, the mail might be virtual
            if mail.name not in repo:
                continue

            this_email = email_get_from(repo.mbox.get_messages(mail.name)[0])[1]
            if this_email != self.mail_from[1]:
                return True
        return False

    def _patches_project(self):
        for affected in self.patch.diff.affected:
            if True in map(lambda x: affected.startswith(x),
                           self.ROOT_DIRS) or \
               affected in self.ROOT_FILES:
                continue
            return False
        return True

    def _analyse_series(self):
        if self.is_patch:
            if self.message_id == self.thread.name or \
               self.message_id in [x.name for x in self.thread.children]:
                self.is_first_patch_in_thread = True
        elif 'Subject' in self.message and \
             MailCharacteristics.REGEX_COVER.match(str(self.message['Subject'])):
            self.is_cover_letter = True

    def _is_from_bot(self):
        email = self.mail_from[1].lower()
        subject = email_get_header_normalised(self.message, 'subject')
        uagent = email_get_header_normalised(self.message, 'user-agent')
        xmailer = email_get_header_normalised(self.message, 'x-mailer')
        x_pw_hint = email_get_header_normalised(self.message, 'x-patchwork-hint')
        potential_bot = email in self.POTENTIAL_BOTS

        if email in self.BOTS:
            return True

        if potential_bot:
            if x_pw_hint == 'ignore':
                return True

            # Mark Brown's bot and lkp
            if subject.startswith('applied'):
                return True

        if self.REGEX_GREG_ADDED.match(subject):
            return True

        # AKPM's bot. AKPM uses s-nail for automated mails, and sylpheed for
        # all other mails. That's how we can easily separate automated mails
        # from real mails. Secondly, akpm acts as bot if the subject contains [merged]
        if email == 'akpm@linux-foundation.org':
            if 's-nail' in uagent or '[merged]' in subject:
                return True
            if 'mm-commits@vger.kernel.org' in self.lists:
                return True

        # syzbot - email format: syzbot-hash@syzkaller.appspotmail.com
        if 'syzbot' in email and 'syzkaller.appspotmail.com' in email:
            return True

        if xmailer == 'tip-git-log-daemon':
            return True

        # Stephen Rothwell's automated emails (TBD: generates false positives)
        if self.is_next and 'sfr@canb.auug.org.au' in email:
            return True

        return False

    def _integrated_correct(self, repo, maintainers_version):
        if maintainers_version is None:
            return

        maintainers = maintainers_version[self.version]
        sections = maintainers.get_sections_by_files(self.patch.diff.affected)
        for section in sections:
            s_lists, s_maintainers, s_reviewers = maintainers.get_maintainers(section)
            s_maintainers = {x[1] for x in s_maintainers if x[1]}
            s_reviewers = {x[1] for x in s_reviewers if x[1]}
            self.maintainers[section] = s_lists, s_maintainers, s_reviewers

        if not self.first_upstream:
            return

        def check_maintainer(section, committer):
            _, s_maintainers, _ = maintainers.get_maintainers(section)
            return committer in [name for name, mail in s_maintainers]

        # In case the patch was integrated, fill the fields committer and
        # integrated_correct. integrated_correct indicates if the patch was
        # integrated by a maintainer that is responsible for a section that is
        # affected by the patch. IOW: The field indicates if the patch was
        # picked by the "correct" maintainer
        upstream = repo[self.first_upstream]
        self.committer = upstream.committer.name.lower()
        self.integrated_correct = False
        self.integrated_xcorrect = False
        sections = maintainers.get_sections_by_files(upstream.diff.affected)
        for section in sections:
            if check_maintainer(section, self.committer):
                self.integrated_correct = True
                self.integrated_xcorrect = True
                break

        if self.integrated_xcorrect or not maintainers.cluster:
            return

        def get_cluster(section):
            for cluster in maintainers.cluster:
                if section in cluster:
                    return cluster
            raise ValueError('Unable to find a cluster for section %s (Version: %s)' % (section, self.version))

        # Search for the cluster
        for section in sections - {'THE REST'}:
            cluster = get_cluster(section)
            for c in cluster:
                self.integrated_xcorrect = check_maintainer(c, self.committer)
                if self.integrated_xcorrect:
                    break

            if self.integrated_xcorrect:
                break

    def list_matches_patch(self, list):
        for lists, _, _ in self.maintainers.values():
            if list in lists:
                return True
        return False

    def _cleanup(self):
        del self.message
        del self.patch

    def __init__(self, repo, clustering, message_id):
        self.message_id = message_id

        self.message = repo.mbox.get_messages(message_id)[0]
        self.thread = repo.mbox.threads.get_thread(message_id)
        self.recipients = email_get_recipients(self.message)

        self.recipients_lists = self.recipients & (repo.mbox.lists | self.LISTS)
        self.recipients_other = self.recipients - (repo.mbox.lists | self.LISTS)

        self.mail_from = email_get_from(self.message)
        self.subject = email_get_header_normalised(self.message, 'Subject')
        self.date = mail_parse_date(self.message['Date'])

        self.lists = repo.mbox.get_lists(message_id)

        # stuff for maintainers analysis
        self.maintainers = dict()

        # Patch characteristics
        self.is_patch = message_id in repo and message_id not in repo.mbox.invalid
        self.patch = None

        self.patches_project = False
        self.has_foreign_response = None
        self.first_upstream = None
        self.committer = None
        self.integrated_correct = None
        self.integrated_xcorrect = None

        self.version = None

        self.is_cover_letter = False
        self.is_first_patch_in_thread = False
        self.is_next = None
        self.process_mail = False

        self.is_from_bot = None
        self._analyse_series()

        # By default, assume type 'other'
        self.type = PatchType.OTHER

        self.is_from_bot = self._is_from_bot()

        if not self.is_patch:
            return

        self.patch = repo[message_id]

        # We must only analyse foreign responses of patches if the patch is
        # the first patch in a thread. Otherwise, we might not be able to
        # determine the original author of a thread. Reason: That mail
        # might be missing.
        if self.is_first_patch_in_thread:
            self.has_foreign_response = self._has_foreign_response(repo)
        elif self.type == PatchType.OTHER:
            self.type = PatchType.NOT_FIRST

        self.process_mail = True in [process in self.subject for process in self.PROCESSES]
        if self.process_mail:
            self.type = PatchType.PROCESS

        self.patches_project = self._patches_project()
        if not self.patches_project:
            self.type = PatchType.NOT_PROJECT
        # Even if the patch does not patch Linux, we can assign it to a
        # appropriate version
        self.version = repo.patch_get_version(self.patch)

        self.first_upstream = get_first_upstream(repo, clustering, message_id)


def _load_mail_characteristic(message_id):
    return message_id, _characteristics_class(_repo, _maintainers_version,
                                              _clustering, message_id)


def load_maintainers_characteristics(config, characteristics_class, clustering,
                                     ids):
    repo = config.repo

    tags = {repo.patch_get_version(repo[x]) for x in clustering.get_downstream()}
    maintainers_version = load_maintainers(config, tags)

    def _load_characteristics(ret):
        if ret is None:
            ret = dict()

        missing = ids - ret.keys()
        if len(missing) == 0:
            return ret, False

        global _repo, _maintainers_version, _clustering, _characteristics_class
        _maintainers_version = maintainers_version
        _clustering = clustering
        _repo = repo
        _characteristics_class = characteristics_class
        p = Pool(processes=int(0.25*cpu_count()), maxtasksperchild=4)

        missing = p.map(_load_mail_characteristic, missing, chunksize=1000)
        missing = dict(missing)
        print('Done')
        p.close()
        p.join()
        _repo = None
        _maintainers_version = None
        _clustering = None
        _characteristics_class = None

        return {**ret, **missing}, True

    log.info('Loading/Updating patch characteristics...')
    characteristics = load_pkl_and_update(config.f_characteristics_pkl,
                                          _load_characteristics)

    return characteristics


def load_characteristics(config, clustering):
    """
    This routine loads characteristics for ALL mails in the time window
    config.mbox_timewindow, and loads multiple instances of maintainers for the
    patches of the clustering.
    """
    from .LinuxMailCharacteristics import LinuxMailCharacteristics
    from .QemuMailCharacteristics import QemuMailCharacteristics
    from .UBootMailCharacteristics import UBootMailCharacteristics
    from .XenMailCharacteristics import XenMailCharacteristics
    _load_characteristics = {
        'linux': (load_maintainers_characteristics, LinuxMailCharacteristics),
        'qemu': (load_maintainers_characteristics, QemuMailCharacteristics),
        'u-boot': (load_maintainers_characteristics, UBootMailCharacteristics),
        'xen': (load_maintainers_characteristics, XenMailCharacteristics),
    }

    repo = config.repo

    # Characteristics need thread information. Ensure it's loaded.
    repo.mbox.load_threads()

    all_messages_in_time_window = repo.mbox.get_ids(config.mbox_time_window,
                                                    allow_invalid=True)

    if config.project_name in _load_characteristics:
        loader, characteristics_class = _load_characteristics[config.project_name]
        return loader(config, characteristics_class, clustering,
                      all_messages_in_time_window)
    else:
        raise NotImplementedError('Missing code for project %s' % config.project_name)
