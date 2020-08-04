#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2020

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import sys
import os
from logging import getLogger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

log = getLogger(__name__[-15:])


def get_cluster_fraction_upstream(cluster, num, geq=False):
    if geq:
        no_clusters = len([d for d, u in cluster if len(u) >= num])
    else:
        no_clusters = len([d for d, u in cluster if len(u) == num])

    return num, no_clusters, 100 * no_clusters / len(cluster)


def get_cluster_fraction_downstream(cluster, num, geq=False):
    if geq:
        no_clusters = len([d for d, u in cluster if len(d) >= num])
    else:
        no_clusters = len([d for d, u in cluster if len(d) == num])

    return num, no_clusters, 100 * no_clusters / len(cluster)


def clusterstats(config, argv):
    _, c = config.load_cluster()

    no_all_mails = len(config.repo.mbox.get_ids(config.mbox_time_window, allow_invalid=True))

    # Erroneous! Doesn't respect time window
    #p = Popen(['./num_mails.sh', project], stdout=PIPE, stderr=PIPE)
    #output, err = p.communicate()
    #num_mails = int(output)

    downstream = c.get_downstream()
    upstream = c.get_upstream()

    no_downstream = len(downstream)
    no_upstream = len(upstream)

    mail_clusters = [(d, u) for d, u in c.iter_split() if len(d) != 0]
    no_mail_clusters = len(mail_clusters)

    mail_clusters_upstream = [(d, u) for d, u in mail_clusters if len(u) != 0]
    no_mail_clusters_upstream = len(mail_clusters_upstream)

    mail_clusters_not_upstream = [(d, u) for d, u in mail_clusters if len(u) == 0]
    no_mail_clusters_not_upstream = len(mail_clusters_not_upstream)

    hashes_assigned = [len(u) for _, u in mail_clusters]

    log.info('           Total mails with patches: %7u' % no_downstream)
    log.info('                      Total commits: %7u' % no_upstream)
    log.info('                      Mail clusters: %7u' % no_mail_clusters)
    log.info('                             #mails: %7u' % no_all_mails)
    log.info('                        patch ratio: %.2f%%' % (no_downstream * 100 / no_all_mails))
    log.info('              patch mails / commits: %.2f' % (no_downstream / no_upstream))
    log.info('')
    log.info('Total number of unassigned clusters: %7u' % no_mail_clusters_not_upstream)
    log.info('Total number of   assigned clusters: %7u' % no_mail_clusters_upstream)
    log.info('')
    log.info('Total number of unassigned messages: %7u' % sum([len(d) for d, _ in mail_clusters_not_upstream]))
    log.info('Total number of   assigned messages: %7u' % sum([len(d) for d, _ in mail_clusters_upstream]))
    log.info('')
    log.info('Percentage of commit hashes in clusters: %.2f%% (aka. commit coverage)' % (100 * sum(hashes_assigned) / no_upstream))
    log.info('     Percentage of clusters with hashes: %.2f%%' % (100 * no_mail_clusters_upstream / no_mail_clusters))
    log.info('')

    for i in range(1, 5):
        log.info('Mail clusters with   %u commit hashes:       %8u (%5.2f%%)' %
              get_cluster_fraction_upstream(mail_clusters_upstream, i, geq=False))
    log.info('Mail clusters with >=%u commit hashes:       %8u (%5.2f%%)' %
          get_cluster_fraction_upstream(mail_clusters_upstream, 5, geq=True))

    log.info('')

    for i in range(1, 5):
        log.info('     Mail clusters with   %u messages:       %8u (%5.2f%%)' %
              get_cluster_fraction_downstream(mail_clusters, i, geq=False))
    log.info('     Mail clusters with >=%u messages:       %8u (%5.2f%%)' %
          get_cluster_fraction_downstream(mail_clusters, 5, geq=True))
