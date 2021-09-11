"""
PaStA - Patch Stack Analysis

Copyright (c) Sebastian Duda, 2021

Author:
  Sebastian Duda <git@sebdu.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .MailCharacteristics import MailCharacteristics


class GitMailCharacteristics(MailCharacteristics):
    # Git has tons of different files in the root directory, which would lead
    # to a huge amount of false negatives if we would track them with ROOT_*
    # variables. Hence, in case of git, assume that every patch patches the
    # project.
    def _patches_project(self):
        return True

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        pass
