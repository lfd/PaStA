"""
PaStA - Patch Stack Analysis

Copyright (c) Sebastian Duda, 2021

Author:
  Sebastian Duda <git@sebdu.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .MailCharacteristics import MailCharacteristics, PatchType


class DPDKMailCharacteristics(MailCharacteristics):
    ROOT_DIRS = ['app',
                 'buildtools',
                 '.ci',
                 'config',
                 'devtools',
                 'doc',
                 'drivers',
                 'examples',
                 'kernel',
                 'lib',
                 'license',
                 'mk',
                 'pkg',
                 'scripts',
                 'test',
                 'tools',
                 'usertools',
    ]
    ROOT_FILES = ['ABI_VERSION',
                  '.git',
                  '.gitattributes',
                  '.gitignore',
                  'GNUmakefile',
                  'LICENSE.GPL',
                  'LICENSE.LGPL',
                  'MAINTAINERS',
                  'Makefile',
                  'meson.build',
                  'meson_options.txt',
                  'README',
                  '.travis.yml',
                  'VERSION',
    ]

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        pass
