"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import email
import re

from .MAINTAINERS import load_maintainers
from .Util import mail_parse_date

VALID_EMAIL_REGEX = re.compile(r'.+@.+\..+')


def email_get_recipients(message):
    recipients = message.get_all('To', []) + message.get_all('Cc', [])
    recipients = list(filter(None, recipients))
    # get_all might return Header objects. Convert them all to strings.
    recipients = [str(x) for x in recipients]

    # Only accept valid email addresses
    recipients = {x[1].lower() for x in email.utils.getaddresses(recipients)
                  if VALID_EMAIL_REGEX.match(x[1])}

    return recipients


def email_get_header_normalised(message, header):
    header = str(message[header] or '').lower()
    header = header.replace('\n', '').replace('\t', ' ')

    return header


def email_get_from(message):
    mail_from = email_get_header_normalised(message, 'From')
    return email.utils.parseaddr(mail_from)

class MailCharacteristics:
    def __init__(self, repo, clustering, message_id):
        self.message_id = message_id

        self.message = repo.mbox.get_messages(message_id)[0]
        self.thread = repo.mbox.threads.get_thread(message_id)
        self.recipients = email_get_recipients(self.message)

        self.recipients_lists = self.recipients & repo.mbox.lists
        self.recipients_other = self.recipients - repo.mbox.lists

        self.mail_from = email_get_from(self.message)
        self.subject = email_get_header_normalised(self.message, 'Subject')
        self.date = mail_parse_date(self.message['Date'])

        self.lists = repo.mbox.get_lists(message_id)


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
