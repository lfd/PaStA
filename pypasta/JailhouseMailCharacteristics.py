"""
PaStA - Patch Stack Analysis

Copyright (c) Sebastian Duda, 2021

Author:
  Sebastian Duda <git@sebdu.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .MailCharacteristics import MailCharacteristics


class JailhouseMailCharacteristics(MailCharacteristics):
    ROOT_DIRS = ['ci',
                 'configs',
                 'Documentation',
                 'driver',
                 'hypervisor',
                 'include',
                 'inmates',
                 'pyjailhouse',
                 'scripts',
                 'samples',
                 'tools',
    ]
    ROOT_FILES = ['CONTRIBUTING.md',
                  'COPYING',
                  'driver.c',
                  'FAQ.md',
                  '.git',
                  '.gitignore',
                  'jailhouse.h',
                  'Kbuild',
                  'LICENSING.md',
                  'Makefile',
                  'README',
                  'README.md',
                  'setup.py',
                  'TODO',
                  'TODO.md',
                  '.travis.yml',
                  'VERSION',
    ]

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        pass
