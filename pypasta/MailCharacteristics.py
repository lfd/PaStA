"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .MAINTAINERS import load_maintainers

class MailCharacteristics:
    def __init__(self, message_id):
        self.message_id = message_id


def load_characteristics(config, clustering):
    """
    This routine loads characteristics for ALL mails in the time window
    config.mbox_timewindow, and loads multiple instances of maintainers for the
    patches of the clustering.
    """
    from .LinuxMailCharacteristics import load_linux_mail_characteristics
    _load_characteristics = {
        'linux': load_linux_mail_characteristics,
    }

    repo = config.repo

    # Characteristics need thread information. Ensure it's loaded.
    repo.mbox.load_threads()

    all_messages_in_time_window = repo.mbox.get_ids(config.mbox_time_window,
                                                    allow_invalid=True)

    if config.project_name in _load_characteristics:
        return _load_characteristics[config.project_name](config, clustering, all_messages_in_time_window)
    else:
        raise NotImplementedError('Missing code for project %s' % config.project_name)
