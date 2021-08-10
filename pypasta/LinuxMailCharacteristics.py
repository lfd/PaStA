"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019-2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import re

from logging import getLogger

from .MailCharacteristics import MailCharacteristics, PatchType, email_get_header_normalised

log = getLogger(__name__[-15:])

MAIL_STRIP_TLD_REGEX = re.compile(r'(.*)\..+')


def ignore_tld(address):
    match = MAIL_STRIP_TLD_REGEX.match(address)
    if match:
        return match.group(1)

    return address


def ignore_tlds(addresses):
    return {ignore_tld(address) for address in addresses if address}


class LinuxMailCharacteristics (MailCharacteristics):
    # Additional lists that are not known by pasta
    LISTS = set()

    REGEX_COMMIT_UPSTREAM = re.compile('.*commit\s+.+\s+upstream.*', re.DOTALL | re.IGNORECASE)
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
                  'MAINTAINERS',
                  'Makefile',
                  'README',
                  'REPORTING-BUGS',
    ]
    ROOT_DIRS = ['arch/',
                 'block/',
                 'certs/',
                 'crypto/',
                 'Documentation/',
                 'drivers/',
                 'firmware/',
                 'fs/',
                 'include/',
                 'init/',
                 'ipc/',
                 'kernel/',
                 'lib/',
                 'LICENSES/',
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
                 'kunit/',
    ]

    HAS_MAINTAINERS = True

    def _is_stable_review(self):
        if 'X-Mailer' in self.message and \
           'LinuxStableQueue' in self.message['X-Mailer']:
            return True

        if 'X-stable' in self.message:
            xstable = self.message['X-stable'].lower()
            if xstable == 'commit' or xstable == 'review':
                return True

        # The patch needs to be sent to the stable list
        if not ('stable' in self.lists or
                'stable@vger.kernel.org' in self.recipients_lists):
            return False

        message_flattened = '\n'.join(self.patch.message).lower()

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

    def _is_next(self):
        if 'linux-next' in self.lists:
            return True

        if 'linux-next@vger.kernel.org' in self.recipients_lists:
            return True

        return False

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        self.is_stable_review = False

        self.is_next = self._is_next()

        # Messages can be received by bots, or linux-next, even if they
        # don't contain patches
        if self.is_from_bot:
            self.type = PatchType.BOT
        elif self.is_next:
            self.type = PatchType.NEXT

        if not self.is_patch:
            return

        self.is_stable_review = self._is_stable_review()
        if self.is_stable_review:
            self.type = PatchType.STABLE
