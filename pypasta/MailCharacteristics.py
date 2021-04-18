"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import csv
import email
import re
from enum import Enum

from .MAINTAINERS import load_maintainers
from .Util import mail_parse_date

VALID_EMAIL_REGEX = re.compile(r'.+@.+\..+')


class PatchType(Enum):
    PATCH = 'patch' # A regular patch written by a human author
    BOT = 'bot'
    NEXT = 'linux-next'
    STABLE = 'stable-review'
    NOT_LINUX = 'not-linux'
    PROCESS = 'process'
    NOT_FIRST = 'not-first' # Mail contains a patch, but it's not the first patch in the thread
    OTHER = 'other'


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
    REGEX_COVER = re.compile('\[.*patch.*\s0+/.*\].*', re.IGNORECASE)

    @staticmethod
    def dump_release_info(config):
        relevant_releases = [
            (tag, date.strftime('%Y-%m-%d')) for tag, date in config.repo.tags if
                config.mbox_mindate < date.replace(tzinfo=None) < config.mbox_maxdate and
                '-rc' not in tag
        ]
        with open(config.f_releases, 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=['release', 'date'])
            writer.writeheader()
            for release, date in relevant_releases:
                writer.writerow({'release': release,
                                 'date': date})

    def _analyse_series(self, thread, message):
        if self.is_patch:
            if self.message_id == thread.name or \
               self.message_id in [x.name for x in thread.children]:
                self.is_first_patch_in_thread = True
        elif 'Subject' in message and \
             MailCharacteristics.REGEX_COVER.match(str(message['Subject'])):
            self.is_cover_letter = True

    def __init__(self, message_id, repo):
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

        # Patch characteristics
        self.is_patch = message_id in repo and message_id not in repo.mbox.invalid

        self.patches_project = False
        self.has_foreign_response = None
        self.is_upstream = None
        self.committer = None
        self.integrated_by_maintainer = None

        self.version = None

        self.is_cover_letter = False
        self.is_first_patch_in_thread = False
        self.process_mail = False

        self.is_from_bot = None
        self._analyse_series(self.thread, self.message)


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
