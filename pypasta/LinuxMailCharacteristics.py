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

from multiprocessing import Pool, cpu_count
from tqdm import tqdm

_repo = None
_maintainers_version = None
_mainline_tags = None

MAINLINE_REGEX = re.compile(r'^v(\d+\.\d+|2\.6\.\d+)(-rc\d+)?$')


def get_recipients(message):
    recipients = message.get_all('To', []) + message.get_all('Cc', [])
    # get_all might return Header objects. Convert them all to strings.
    recipients = [str(x) for x in recipients]
    recipients = {x[1] for x in email.utils.getaddresses(recipients)}

    return recipients


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
        if 'From' not in message:
            return False
        mail_from = str(message['From'])

        bots = ['broonie@kernel.org', 'lkp@intel.com']

        if 'X-Patchwork-Hint' in message and \
            message['X-Patchwork-Hint'] == 'ignore':
            if True in [bot in mail_from for bot in bots]:
                return True

        # The Tip bot
        if 'tipbot@zytor.com' in mail_from or \
           'noreply@ciplatform.org' in mail_from:
            return True

        # Stephen Rothwell's automated emails
        if self.is_next and 'sfr@canb.auug.org.au' in mail_from:
            return True

        return False

    @staticmethod
    def patch_get_version(patch):
        author_date = patch.author.date
        tag = None

        for cand_tag, cand_tag_date in _mainline_tags:
            if cand_tag_date > author_date:
                break
            tag = cand_tag

        if tag is None:
            raise RuntimeError('No valid tag found for patch %s' % patch.id)

        return tag

    def check_maintainer(self, repo, maintainer, message_id):
        message = repo.mbox.get_messages(message_id)[0]
        patch = repo[message_id]

        recipients = get_recipients(message)
        subsystems = maintainer.get_subsystems_by_files(patch.diff.affected)

        # Ignore THE REST subsystem
        subsystems.discard('THE REST')

        lists = set()
        maintainers = set()

        for subsystem in subsystems:
            s_lists, s_mtrs = maintainer.get_maintainers(subsystem)
            lists |= s_lists
            s_mtrs = {x[1] for x in s_mtrs}
            maintainers |= s_mtrs

        recipients_should = lists | maintainers

        correctly_adressed = recipients & recipients_should

        self.maintainers_all = correctly_adressed == recipients_should
        self.maintainers_some = len(correctly_adressed) != 0

    @staticmethod
    def _is_stable_review(lists_of_patch, recipients, patch):
        # The patch needs to be sent to the stable list
        if not ('stable' in lists_of_patch or \
           'stable@vger.kernel.org' in recipients):
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

    @staticmethod
    def flatten_recipients(message):
        addresses = str()
        if 'To' in message:
            addresses += str(message['To'])
        if 'Cc' in message:
            addresses += '\n' + str(message['Cc'])
        addresses = addresses.replace('\n', ' ')
        return addresses

    @staticmethod
    def _is_next(lists_of_patch, recipients):
        if 'linux-next' in lists_of_patch:
            return True

        if 'linux-next@vger.kernel.org' in recipients:
            return True

        return False

    def _analyse_series(self, repo, message_id, message):
        thread = repo.mbox.threads.get_thread(message_id)
        if self.is_patch:
            if message_id == thread.name or \
               message_id in [x.name for x in thread.children]:
                self.is_first_patch_in_thread = True
        elif 'Subject' in message and \
             LinuxMailCharacteristics.REGEX_COVER.match(str(message['Subject'])):
            self.is_cover_letter = True

    def __init__(self, repo, maintainers_version, message_id):
        self.is_stable_review = False
        self.patches_linux = False
        self.is_patch = False

        self.linux_version = None
        self.maintainers_all = None
        self.maintainers_some = None

        self.is_cover_letter = False
        self.is_first_patch_in_thread = False

        message = repo.mbox.get_messages(message_id)[0]
        lists_of_patch = repo.mbox.get_lists(message_id)
        recipients = LinuxMailCharacteristics.flatten_recipients(message)

        self.is_next = self._is_next(lists_of_patch, recipients)
        if message_id in repo and message_id not in repo.mbox.invalid:
            self.is_patch = True
            patch = repo[message_id]
            self.patches_linux = self._patches_linux(patch)
            self.is_stable_review = self._is_stable_review(lists_of_patch,
                                                           recipients, patch)

            if self.patches_linux and maintainers_version is not None:
                self.linux_version = self.patch_get_version(patch)
                maintainers = maintainers_version[self.linux_version]
                self.check_maintainer(repo, maintainers, message_id)

        self.is_from_bot = self._is_from_bot(message)

        self._analyse_series(repo, message_id, message)


def _load_mail_characteristic(message_id):
    return message_id, LinuxMailCharacteristics(_repo, _maintainers_version,
                                                message_id)


def load_linux_mail_characteristics(repo, message_ids,
                                    maintainers_version=None):
    ret = dict()

    global _mainline_tags
    _mainline_tags = list(filter(lambda x: MAINLINE_REGEX.match(x[0]), repo.tags))

    global _repo, _maintainers_version
    _maintainers_version = maintainers_version
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

    return ret
