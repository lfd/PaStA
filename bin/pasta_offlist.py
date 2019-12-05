"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019

Authors:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

from logging import getLogger

from pypasta import *
from pypasta.LinuxMaintainers import load_maintainers
from pypasta.Util import get_commit_hash_range

log = getLogger(__name__[-15:])


def get_youngest_commit(repo, commits):
    commits = list(commits)
    youngest = commits[0]
    youngest_date = repo[youngest].committer.date

    for commit in commits[1:]:
        date = repo[commit].committer.date
        if date > youngest_date:
            youngest = commit
            youngest_date = date

    return youngest


def offlist(config, prog, argv):
    if config.mode != config.Mode.MBOX:
        log.error('Only works in Mbox mode!')
        return -1

    if config.mbox_use_patchwork_id:
        log.error('pasta evaluate_patches does not work with '
                  'USE_PATCHWORK_ID = true')

    repo = config.repo
    _, clustering = config.load_cluster()
    clustering.optimize()

    config.load_ccache_mbox()
    repo.mbox.load_threads()

    patches = set()
    upstream = set()
    for d, u in clustering.iter_split():
        patches |= d
        upstream |= u

    all_messages_in_time_window = repo.mbox.get_ids(config.mbox_time_window,
                                                    allow_invalid=True)

    ####
    rc_commits = set()
    for version in range(0, 5):
        rc_commits |= set(get_commit_hash_range(config.repo_location, 'v5.%u-rc1..v5.%u' % (version, version)))
    #####

    #tags = {x[0] for x in repo.tags if not x[0].startswith('v2.6')}
    #tags |= {x[0] for x in repo.tags if x[0].startswith('v2.6.39')}
    tags = {x[0] for x in repo.tags if x[0].startswith('v5.')}
    maintainers_version = load_maintainers(config, tags)
    characteristics = \
        load_linux_mail_characteristics(config, maintainers_version, clustering,
                                        all_messages_in_time_window)


    stats_no_upstream = 0
    clustering_result = Clustering()

    by_committer = dict()
    by_author = dict()

    def add_to_dict(dct, mail, content):
        if mail not in dct:
            dct[mail] = set()

        dct[mail].add(content)

    def write_dict(dct, filename):
        as_list = list(dct.items())
        as_list.sort(key=lambda x: len(x[1]))

        with open(filename, 'w') as f:
            for mail, elems in as_list:
                f.write('%s (%u):\n' % (mail, len(elems)))
                for elem in elems:
                    f.write('  %s\n' % elem)
                f.write('\n')

    for downstream, upstream in clustering.iter_split():
        len_orig = len(downstream)

        # We're not interested in clusters with no upstream hash
        if len(upstream) == 0:
            stats_no_upstream += 1
            continue

        if len(upstream) > 1:
            log.info('More than one upstream: %s' % upstream)
            continue

        # Across downstream patches: filter for backports and for next patches
        # or patches from bots
        downstream = {x for x in downstream if
                      not characteristics[x].is_stable_review}

        # We must NOT exclude bots. E.g., bots DO write patches that are
        # accepted E.g., kbuild test robot write coccinelle patches.
        #downstream = {x for x in downstream if
        #              not characteristics[x].is_from_bot}
        downstream = {x for x in downstream if
                      not characteristics[x].is_next}

        upstream = get_youngest_commit(repo, upstream)
        print(downstream)
        print(upstream)
        upstream_commit_date = repo[upstream].committer.date

        cluster = downstream | {upstream}
        print(cluster)
        clustering_result.insert(*cluster)
        clustering_result.mark_upstream(upstream)

        if len(downstream) == 0:
            patch = repo[upstream]
            add_to_dict(by_author, patch.author.email, upstream)
            add_to_dict(by_committer, patch.committer.email, upstream)

        #if upstream not in rc_commits:
        #    continue

    f_result = '/tmp/cluster'
    log.info('Saving resulting cluster to %s' % f_result)
    clustering_result.to_file(f_result)

    write_dict(by_committer, '/tmp/by_committer')
    write_dict(by_author, '/tmp/by_author')

    log.info('Some stats:')
    log.info('  Skipped no upstream: %u' % stats_no_upstream)
