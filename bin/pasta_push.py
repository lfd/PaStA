"""
PaStA - Patch Stack Analysis

Copyright (C) 2019, Bayerische Motoren Werke Aktiengesellschaft (BMW AG)

Author:
  Mete Polat <metepolat2000@gmail.com>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from logging import getLogger

import argparse
from shutil import copyfile

from pypasta import Clustering

log = getLogger('Patchwork.push')


def push(config, prog, argv):
    description = 'Update patch relations and commit upstream references on ' \
                  'patchwork '
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument('-ignore-relations', action='store_true',
                        help='Do not update patch relations')
    parser.add_argument('-ignore-commits', action='store_true',
                        help='Do not update commit references')
    args = parser.parse_args(argv)

    ignore_relations = args.ignore_relations
    ignore_commits = args.ignore_commits

    if ignore_relations and ignore_commits:
        log.info('Nothing to update')
        return

    try:
        cluster_cached = Clustering.from_file(
            config.f_clustering_cache, must_exist=True)
    except FileNotFoundError:
        cluster_cached = None

    _, cluster = config.load_cluster()

    config.repo.mbox.register_patchwork(config)

    if cluster_cached is not None:
        Clustering.remove_identical(cluster, cluster_cached)

    mbox = config.repo.mbox
    patchwork = mbox.patchwork
    index = mbox.mbox_raw.index

    commit_count = 0
    relation_count = 0

    log.info('Pushing to patchwork')

    for relation in cluster:
        if len(relation) < 2:
            # message is not related to anything else and has no commit_ref
            continue

        commits = relation & cluster.upstream
        # pick one upstream_commit
        commit = commits.pop() if len(commits) > 0 else None
        related = relation - {commit}

        patchwork_id = None
        if commit:
            # Find the most recent patch in the relation for setting the
            # upstream commit on it (key = date of msg)
            latest_msg_id = max(related, key=lambda msg_id: index[msg_id][0][0])
            patchwork_id = mbox[latest_msg_id].patchwork_id

        if not ignore_commits and commit:
            patchwork.update_commit_ref(patchwork_id, commit)
            commit_count += 1

        patches = [mbox[msg_id].patchwork_id for msg_id in related]
        if not ignore_relations:
            patchwork.insert_relation(patches)
            relation_count += 1

    log.info('  ↪ done')
    log.info('Created %d relations and set %d commit references' %
             (relation_count, commit_count))

    log.info('Caching updated relations and commit references')
    copyfile(config.f_clustering, config.f_clustering_cache)
    log.info('  ↪ done')
