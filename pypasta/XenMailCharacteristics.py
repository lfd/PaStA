"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .MailCharacteristics import MailCharacteristics, PatchType


class XenMailCharacteristics(MailCharacteristics):
    ROOT_DIRS = ['config/',
                 'docs/',
                 'stubdom/',
                 'tools/',
                 'xen/',
                 'automation/',
                 'm4/',
                 'misc/',
                 'scripts/',
    ]
    ROOT_FILES = ['.cirrus.yml',
                  '.gitarchive-info',
                  '.gitattributes',
                  '.gitignore',
                  '.gitlab-ci.yml',
                  '.hgignore',
                  '.hgsigs',
                  '.hgtags',
                  'CHANGELOG.md',
                  'CODING_STYLE',
                  'CONTRIBUTING',
                  'COPYING',
                  'CREDITS',
                  'Config.mk',
                  'INSTALL',
                  'MAINTAINERS',
                  'Makefile',
                  'README',
                  'SUPPORT.md',
                  'autogen.sh',
                  'config.guess',
                  'config.sub',
                  'configure',
                  'configure.ac',
                  'install.sh',
                  'version.sh',
    ]

    HAS_MAINTAINERS = True

    # Additional lists that are not known by pasta
    LISTS = {'osstest-admin@xenproject.org',
             'security@xen.org',
             'xen-api@lists.xenproject.org',
             'xen-devel@lists.xen.org',
             'xen-devel@lists.xensource.com',
             'xen-users@lists.xenproject.org',
    }

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        pass
