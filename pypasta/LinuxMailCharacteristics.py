"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019-2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import csv
import re

from enum import Enum
from anytree import LevelOrderIter
from logging import getLogger
from multiprocessing import Pool, cpu_count

from .MAINTAINERS import load_maintainers
from .MailCharacteristics import MailCharacteristics, email_get_header_normalised, email_get_from
from .Util import get_first_upstream, mail_parse_date, load_pkl_and_update

log = getLogger(__name__[-15:])

_repo = None
_maintainers_version = None
_clustering = None

MAIL_STRIP_TLD_REGEX = re.compile(r'(.*)\..+')


def ignore_tld(address):
    match = MAIL_STRIP_TLD_REGEX.match(address)
    if match:
        return match.group(1)

    return address


def ignore_tlds(addresses):
    return {ignore_tld(address) for address in addresses if address}


# TBD, leave more comments here
class LinuxPatchType(Enum):
    PATCH = 'patch' # A regular patch written by a human author
    BOT = 'bot'
    NEXT = 'linux-next'
    STABLE = 'stable-review'
    NOT_PROJECT = 'not-project'
    PROCESS = 'process'
    NOT_FIRST = 'not-first' # Mail contains a patch, but it's not the first patch in the thread
    OTHER = 'other'


class LinuxMailCharacteristics (MailCharacteristics):
    BOTS = {'tip-bot2@linutronix.de', 'tipbot@zytor.com',
            'noreply@ciplatform.org', 'patchwork@emeril.freedesktop.org'}
    POTENTIAL_BOTS = {'broonie@kernel.org', 'lkp@intel.com'}

    REGEX_COMMIT_UPSTREAM = re.compile('.*commit\s+.+\s+upstream.*', re.DOTALL | re.IGNORECASE)
    REGEX_GREG_ADDED = re.compile('patch \".*\" added to .*')
    ROOT_FILES = ['.clang-format',
                  '.cocciconfig',
                  '.get_maintainer.ignore',
                  '.gitignore',
                  '.gitattributes',
                  '.mailmap',
                  'COPYING',
                  'CREDITS',
                  'Kbuild',
                  'Kconfig',
                  'README',
                  'MAINTAINERS',
                  'Makefile']
    ROOT_DIRS = ['Documentation/',
                 'LICENSES/',
                 'arch/',
                 'block/',
                 'certs/',
                 'crypto/',
                 'drivers/',
                 'fs/',
                 'include/',
                 'init/',
                 'ipc/',
                 'kernel/',
                 'lib/',
                 'mm/',
                 'net/',
                 'samples/',
                 'scripts/',
                 'security/',
                 'sound/',
                 'tools/',
                 'usr/',
                 'virt/',
                 # not yet merged subsystems
                 'kunit/']

    def _is_from_bot(self, message):
        email = self.mail_from[1].lower()
        subject = email_get_header_normalised(message, 'subject')
        uagent = email_get_header_normalised(message, 'user-agent')
        xmailer = email_get_header_normalised(message, 'x-mailer')
        x_pw_hint = email_get_header_normalised(message, 'x-patchwork-hint')
        potential_bot = email in LinuxMailCharacteristics.POTENTIAL_BOTS

        if email in LinuxMailCharacteristics.BOTS:
            return True

        if potential_bot:
            if x_pw_hint == 'ignore':
                return True

            # Mark Brown's bot and lkp
            if subject.startswith('applied'):
                return True

        if LinuxMailCharacteristics.REGEX_GREG_ADDED.match(subject):
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

    def _has_foreign_response(self, repo, thread):
        """
        This function will return True, if there's another author in this
        thread, other than the ORIGINAL author. (NOT the author of this
        email)
        """
        if len(thread.children) == 0:
            return False  # If there is no response the check is trivial

        for mail in list(LevelOrderIter(thread)):
            # Beware, the mail might be virtual
            if mail.name not in repo:
                continue

            this_email = email_get_from(repo.mbox.get_messages(mail.name)[0])[1]
            if this_email != self.mail_from[1]:
                return True
        return False

    def _is_stable_review(self, message, patch):
        if 'X-Mailer' in message and \
           'LinuxStableQueue' in message['X-Mailer']:
            return True

        if 'X-stable' in message:
            xstable = message['X-stable'].lower()
            if xstable == 'commit' or xstable == 'review':
                return True

        # The patch needs to be sent to the stable list
        if not ('stable' in self.lists or
                'stable@vger.kernel.org' in self.recipients_lists):
            return False

        message_flattened = '\n'.join(patch.message).lower()

        if 'review patch' in message_flattened:
            return True

        if 'upstream commit' in message_flattened:
            return True

        # Greg uses this if the patch doesn't apply to a stable tree
        if 'the patch below does not apply to the' in message_flattened:
            return True

        if LinuxMailCharacteristics.REGEX_COMMIT_UPSTREAM.match(message_flattened):
            return True

        return False

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

    @staticmethod
    def _patches_project(patch):
        for affected in patch.diff.affected:
            if True in map(lambda x: affected.startswith(x),
                           LinuxMailCharacteristics.ROOT_DIRS) or \
               affected in LinuxMailCharacteristics.ROOT_FILES:
                continue

            return False

        return True

    def _is_next(self):
        if 'linux-next' in self.lists:
            return True

        if 'linux-next@vger.kernel.org' in self.recipients_lists:
            return True

        return False

    def list_matches_patch(self, list):
        for lists, _, _ in self.maintainers.values():
            if list in lists:
                return True
        return False

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.is_stable_review = False
        # By default, assume type 'other'
        self.type = LinuxPatchType.OTHER

        # stuff for maintainers analysis
        self.maintainers = dict()

        self.is_next = self._is_next()
        self.is_from_bot = self._is_from_bot(self.message)

        # Messages can be received by bots, or linux-next, even if they
        # don't contain patches
        if self.is_next:
            self.type = LinuxPatchType.NEXT
        elif self.is_from_bot:
            self.type = LinuxPatchType.BOT

        if not self.is_patch:
            return

        patch = repo[message_id]
        self.patches_project = self._patches_project(patch)
        self.is_stable_review = self._is_stable_review(self.message, patch)
        if self.is_stable_review:
            self.type = LinuxPatchType.STABLE

        # We must only analyse foreign responses of patches if the patch is
        # the first patch in a thread. Otherwise, we might not be able to
        # determine the original author of a thread. Reason: That mail
        # might be missing.
        if self.is_first_patch_in_thread:
            self.has_foreign_response = self._has_foreign_response(repo, self.thread)
        elif self.type == LinuxPatchType.OTHER:
            self.type = LinuxPatchType.NOT_FIRST

        # Even if the patch does not patch Linux, we can assign it to a
        # appropriate version
        self.version = repo.linux_patch_get_version(patch)

        # Exit, if we don't patch the project
        if not self.patches_project:
            self.type = LinuxPatchType.NOT_PROJECT
            return

        upstream = clustering.get_upstream(message_id)
        if clustering is not None:
            self.is_upstream = len(upstream) != 0

        processes = ['linux-next', 'git pull', 'rfc']
        self.process_mail = True in [process in self.subject for process in processes]
        if self.process_mail:
            self.type = LinuxPatchType.PROCESS

        # Now we can say it's a regular patch, if we still have the type 'other'
        if self.type == LinuxPatchType.OTHER:
            self.type = LinuxPatchType.PATCH

        if maintainers_version is None:
            return

        maintainers = maintainers_version[self.version]
        sections = maintainers.get_sections_by_files(patch.diff.affected)
        for section in sections:
            s_lists, s_maintainers, s_reviewers = maintainers.get_maintainers(section)
            s_maintainers = {x[1] for x in s_maintainers if x[1]}
            s_reviewers = {x[1] for x in s_reviewers if x[1]}
            self.maintainers[section] = s_lists, s_maintainers, s_reviewers

        if not self.is_upstream:
            return

        # In case the patch was integrated, fill the fields committer
        # and integrated_by_maintainer. integrated_by_maintainer indicates
        # if the patch was integrated by a maintainer that is responsible
        # for a section that is affected by the patch. IOW: The field
        # indicates if the patch was picked by the "correct" maintainer
        upstream = get_first_upstream(repo, clustering, message_id)
        upstream = repo[upstream]
        self.committer = upstream.committer.name.lower()
        self.integrated_by_maintainer = False
        for section in maintainers.get_sections_by_files(upstream.diff.affected):
            _, s_maintainers, _ = maintainers.get_maintainers(section)
            if self.committer in [name for name, mail in s_maintainers]:
                self.integrated_by_maintainer = True
                break


def _load_mail_characteristic(message_id):
    return message_id, LinuxMailCharacteristics(_repo, _maintainers_version,
                                                _clustering, message_id)


def load_linux_mail_characteristics(config, clustering,
                                    ids):
    repo = config.repo

    tags = {repo.linux_patch_get_version(repo[x]) for x in clustering.get_downstream()}
    maintainers_version = load_maintainers(config, tags)

    def _load_characteristics(ret):
        if ret is None:
            ret = dict()

        missing = ids - ret.keys()
        if len(missing) == 0:
            return ret, False

        global _repo, _maintainers_version, _clustering
        _maintainers_version = maintainers_version
        _clustering = clustering
        _repo = repo
        p = Pool(processes=int(cpu_count()), maxtasksperchild=1)

        missing = p.map(_load_mail_characteristic, missing, chunksize=1000)
        missing = dict(missing)
        print('Done')
        p.close()
        p.join()
        _repo = None
        _maintainers_version = None
        _clustering = None

        return {**ret, **missing}, True

    log.info('Loading/Updating Linux patch characteristics...')
    characteristics = load_pkl_and_update(config.f_characteristics_pkl,
                                          _load_characteristics)

    return characteristics
