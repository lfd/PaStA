"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import email
import re

from anytree import LevelOrderIter
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

from .Util import mail_parse_date

_repo = None
_maintainers_version = None
_mainline_tags = None
_clustering = None

MAINLINE_REGEX = re.compile(r'^v(\d+\.\d+|2\.6\.\d+)(-rc\d+)?$')
VALID_EMAIL_REGEX = re.compile(r'.+@.+\..+')


def email_get_recipients(message):
    recipients = message.get_all('To', []) + message.get_all('Cc', [])
    recipients = list(filter(None, recipients))
    # get_all might return Header objects. Convert them all to strings.
    recipients = [str(x) for x in recipients]

    # Only accept valid email addresses
    recipients = {x[1].lower() for x in email.utils.getaddresses(recipients)
                  if VALID_EMAIL_REGEX.match(x[1])}

    return recipients


def email_get_from(message):
    return email.utils.parseaddr(str(message['From'] or '').lower())


class LinuxMailCharacteristics:
    REGEX_COMMIT_UPSTREAM = re.compile('.*commit\s+.+\s+upstream.*', re.DOTALL | re.IGNORECASE)
    REGEX_COVER = re.compile('\[.*patch.*\s0+/.*\].*', re.IGNORECASE)
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
        bots = ['broonie@kernel.org', 'lkp@intel.com']
        potential_bot = True in [bot in self.mail_from[1] for bot in bots]

        if message['X-Patchwork-Hint'] == 'ignore' and potential_bot:
            return True

        if potential_bot and str(message['Subject']).lower().startswith('applied'):
            return True

        # The Tip bot
        if 'tipbot@zytor.com' in self.mail_from[1] or \
           'noreply@ciplatform.org' in self.mail_from[1]:
            return True

        if message['X-Mailer'] == 'tip-git-log-daemon':
            return True

        # Stephen Rothwell's automated emails
        if self.is_next and 'sfr@canb.auug.org.au' in self.mail_from[1]:
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

    def _patch_get_version(self):
        tag = None

        for cand_tag, cand_tag_date in _mainline_tags:
            if cand_tag_date > self.date:
                break
            tag = cand_tag

        if tag is None:
            raise RuntimeError('No valid tag found for patch %s' % self.message_id)

        return tag

    def get_maintainer(self, maintainer, patch):
        subsystems = maintainer.get_subsystems_by_files(patch.diff.affected)
        for subsystem in subsystems:
            s_list, s_maintainer, s_reviewers = maintainer.get_maintainers(subsystem)
            s_maintainer = {x[1] for x in s_maintainer if x[1]}
            s_reviewers = {x[1] for x in s_reviewers if x[1]}
            self.maintainers[subsystem] = s_list, s_maintainer, s_reviewers

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
                'stable@vger.kernel.org' in self.recipients):
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
    def _patches_linux(patch):
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

        if 'linux-next@vger.kernel.org' in self.recipients:
            return True

        return False

    def _analyse_series(self, thread, message):
        if self.is_patch:
            if self.message_id == thread.name or \
               self.message_id in [x.name for x in thread.children]:
                self.is_first_patch_in_thread = True
        elif 'Subject' in message and \
             LinuxMailCharacteristics.REGEX_COVER.match(str(message['Subject'])):
            self.is_cover_letter = True

    def __init__(self, repo, maintainers_version, clustering, message_id):
        self.message_id = message_id
        self.is_patch = message_id in repo and message_id not in repo.mbox.invalid
        self.is_stable_review = False
        self.patches_linux = False
        self.has_foreign_response = None
        self.is_upstream = None

        self.linux_version = None

        self.is_cover_letter = False
        self.is_first_patch_in_thread = False
        self.process_mail = False

        self.maintainers = dict()

        message = repo.mbox.get_messages(message_id)[0]
        thread = repo.mbox.threads.get_thread(message_id)
        self.recipients = email_get_recipients(message)

        self.mail_from = email_get_from(message)
        self.subject = str(message['Subject'] or '').lower()
        self.date = mail_parse_date(message['Date'])

        self.lists = repo.mbox.get_lists(message_id)
        self.is_next = self._is_next()

        self.is_from_bot = self._is_from_bot(message)
        self._analyse_series(thread, message)

        if self.is_patch:
            patch = repo[message_id]
            self.patches_linux = self._patches_linux(patch)
            self.is_stable_review = self._is_stable_review(message, patch)

            # We must only analyse foreign responses of patches if the patch is
            # the first patch in a thread. Otherwise, we might not be able to
            # determine the original author of a thread. Reason: That mail
            # might be missing.
            if self.is_first_patch_in_thread:
                self.has_foreign_response = self._has_foreign_response(repo, thread)

            if self.patches_linux:
                self.is_upstream = len(clustering.get_upstream(message_id)) != 0

                processes = ['linux-next', 'git pull', 'rfc']
                self.process_mail = True in [process in self.subject for process in processes]

                if maintainers_version is not None:
                    self.linux_version = self._patch_get_version()
                    maintainers = maintainers_version[self.linux_version]
                    self.get_maintainer(maintainers, patch)


def _load_mail_characteristic(message_id):
    return message_id, LinuxMailCharacteristics(_repo, _maintainers_version,
                                                _clustering, message_id)


def load_linux_mail_characteristics(repo, message_ids,
                                    maintainers_version=None,
                                    clustering=None):
    ret = dict()

    global _mainline_tags
    _mainline_tags = list(filter(lambda x: MAINLINE_REGEX.match(x[0]), repo.tags))

    global _repo, _maintainers_version, _clustering
    _maintainers_version = maintainers_version
    _clustering = clustering
    _repo = repo
    p = Pool(processes=cpu_count())
    for message_id, characteristics in \
        tqdm(p.imap_unordered(_load_mail_characteristic, message_ids),
                              total=len(message_ids),
                              desc='Linux Mail Characteristics'):
        ret[message_id] = characteristics
    p.close()
    p.join()
    _repo = None
    _maintainers_version = None
    _clustering = None

    return ret
