"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Authors:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import anytree

from logging import getLogger

from pypasta import *
from pypasta.MailCharacteristics import PatchType, email_get_from
from pypasta.Util import mail_parse_date

log = getLogger(__name__[-15:])

_repo = None
_config = None


def hannover(config, argv):
    if config.mode != config.Mode.MBOX:
        log.error("Only works in Mbox mode!")
        return -1

    _, clustering = config.load_cluster()
    clustering.optimize()

    with open('commits-hannover', 'r') as f:
        commits = f.read().split()

    # TBD remove this
    commits = commits[0:50]

    downstreams = set()
    for commit in commits:
        downstreams |= clustering.get_downstream(commit)

    log.info('Need to cache characteristics for %d mails' % len(downstreams))

    #config.load_ccache_mbox()
    characteristics = load_characteristics(config, clustering, downstreams)

    result = open('result.csv', 'w')
    result.write('commit_hash,mails_total,authors_total,first_mail,last_mail,max_height\n')

    repo = config.repo
    mbox = repo.mbox
    threads = mbox.threads

    for commit in commits:
        downstream = clustering.get_downstream(commit)

        # filter for regular patches written by humans
        downstream = {x for x in downstream if characteristics[x].type == PatchType.PATCH}

        first_mail = mail_parse_date('2050-01-01 00:00')
        last_mail = mail_parse_date('1970-01-01 00:00')
        max_height = 0
        mails_total = 0

        if len(downstream) == 0:
            result.write('%s,0,0,NA,NA,0,0\n' % commit)
            continue

        authors = set()

        for d in downstream:
            thread = threads.get_thread(d, subthread=True)
            threads.pretty_print(thread)

            if thread.height > max_height:
                max_height = thread.height

            for node in anytree.PreOrderIter(thread):
                # Even if we didn't capture the real mail, we can count it
                mails_total += 1

                msg_id = node.name

                try:
                    msg = mbox.get_messages(msg_id)[0]
                except:
                    print('Missing Message: %s' % msg_id)
                    continue

                date = mail_parse_date(msg['Date'])

                if date < first_mail:
                    first_mail = date

                if date > last_mail:
                    last_mail = date

                # Use the email address (index 1) as identifier
                authors.add(email_get_from(msg)[1])

        result.write('%s,%d,%d,%s,%s,%d\n' %
                     (commit,
                      mails_total,
                      len(authors),
                      first_mail.strftime('%04Y/%m/%d'),
                      last_mail.strftime('%04Y/%m/%d'),
                      max_height,
        ))

    result.close()