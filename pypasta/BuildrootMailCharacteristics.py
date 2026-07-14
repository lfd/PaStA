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
                 '.github',
                 '.gitlab',
                 'linux',
                 'make',
                 'package',
                 'project',
                 'scripts',
                 'sources',
                 'support',
                 'system',
                 'target',
                 'toolchain',
                 'tools',
                 'utils',
    ]
    ROOT_FILES = ['.b4-config',
                  'boa.mk',
                  'buildroot-documentation.html',
                  'busybox.mk',
                  'CHANGES',
                  '.checkpackageignore',
                  '.clang-format',
                  'Config.in',
                  'Config.in.legacy',
                  'COPYING',
                  '.cvsignore',
                  '.defconfig',
                  'defconfig',
                  'DEVELOPERS',
                  '.editorconfig',
                  '.flake8',
                  'foo',
                  '.git',
                  '.gitignore',
                  '.gitlab-ci.yml',
                  '.gitlab-ci.yml.in',
                  'Makefile',
                  'Makefile.legacy',
                  'README',
                  'README.patches',
                  'SECURITY.md',
                  '.shellcheckrc',
                  'stylesheet.css',
                  'tiny.c',
                  'TODO',
    ]

    # Additional lists that are not known by pasta
    LISTS = {'buildroot@busybox.net',
             'buildroot@uclibc.org',
    }

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        pass
