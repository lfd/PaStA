"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import re


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

        # The Tip bot
        mail_from = str(message['From'])
        if 'tipbot@zytor.com' in mail_from or \
           'noreply@ciplatform.org' in mail_from:
            return True

        # Stephen Rothwell's automated emails
        if self.is_next and 'sfr@canb.auug.org.au' in mail_from:
            return True

        return False

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
        elif LinuxMailCharacteristics.REGEX_COVER.match(message['Subject']):
            self.is_cover_letter = True

    def __init__(self, repo, message_id):
        self.is_stable_review = False
        self.patches_linux = False
        self.is_patch = False

        self.is_cover_letter = False
        self.is_first_patch_in_thread = False

        message = repo.mbox.get_messages(message_id)[0]
        lists_of_patch = repo.mbox.get_lists(message_id)
        recipients = LinuxMailCharacteristics.flatten_recipients(message)

        self.is_next = self._is_next(lists_of_patch, recipients)
        if message_id in repo and message_id not in repo.mbox.invalid:
            self.is_patch = True
            patch = repo[message_id]
            self.is_stable_review = self._is_stable_review(lists_of_patch, recipients, patch)
            self.patches_linux = self._patches_linux(patch)

        self.is_from_bot = self._is_from_bot(message)

        self._analyse_series(repo, message_id, message)
