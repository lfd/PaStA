"""
PaStA - Patch Stack Analysis

Copyright (c) Sebastian Duda, 2021

Author:
  Sebastian Duda <git@sebdu.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .MailCharacteristics import MailCharacteristics


class OpenembeddedMailCharacteristics(MailCharacteristics):
    ROOT_DIRS = ['contrib',
                 'meta',
                 'meta-demoapps',
                 'meta-selftest',
                 'meta-skeleton',
                 'scripts',
    ]
    ROOT_FILES = ['.git',
                  '.gitignore',
                  'LICENSE',
                  'LICENSE.GPL-2.0-only',
                  'LICENSE.MIT',
                  'MAINTAINERS.md',
                  'MEMORIAM',
                  'oe-init-build-env',
                  'oe-init-build-env-memres',
                  'README',
                  'README.LSB',
                  'README.OE-Core',
                  'README.OE-Core.md',
                  'README.qemu',
                  'README.qemu.md',
                  '.templateconf',
    ]

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        pass
