"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2020

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .LinuxMailCharacteristics import load_linux_mail_characteristics
from .LinuxMaintainers import load_maintainers


def load_characteristics_and_maintainers(config, clustering):
    """
    This routine loads characteristics for ALL mails in the time window config.mbox_timewindow, and loads multiple
    instances of maintainers for the the patches of the clustering.

    Returns the characteristics and maintainers_version
    """
    repo = config.repo
    repo.mbox.load_threads()

    all_messages_in_time_window = repo.mbox.get_ids(config.mbox_time_window,
                                                    allow_invalid=True)

    tags = {repo.linux_patch_get_version(repo[x]) for x in clustering.get_downstream()}
    maintainers_version = load_maintainers(config, tags)
    characteristics = \
        load_linux_mail_characteristics(config, maintainers_version, clustering,
                                        all_messages_in_time_window)

    return characteristics, maintainers_version

