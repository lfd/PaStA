"""
PaStA - Patch Stack Analysis

Copyright (c) Sebastian Duda, 2021

Author:
  Sebastian Duda <git@sebdu.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .MailCharacteristics import MailCharacteristics


class BuildrootMailCharacteristics(MailCharacteristics):
    ROOT_DIRS = ['arch',
                 'board',
                 'boot',
                 'configs',
                 'docs',
                 'fs',
                 'linux',
                 'package',
                 'project',
                 'scripts',
                 'sources',
                 'support',
                 'system',
                 'target',
                 'toolchain',
                 'utils',
    ]
    ROOT_FILES = ['boa.mk',
                  'busybox.mk',
                  'CHANGES',
                  'Config.in',
                  'Config.in.legacy',
                  'COPYING',
                  '.defconfig',
                  'DEVELOPERS',
                  '.flake8',
                  '.git',
                  '.gitignore',
                  '.gitlab-ci.yml',
                  '.gitlab-ci.yml.in',
                  'Makefile',
                  'Makefile.legacy',
                  'README',
                  'TODO',
    ]

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        pass
