"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2017-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import os
import sys

from logging import getLogger
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *

log = getLogger(__name__[-15:])
repo = None


def get_youngest(repo, commits, commit_date):
    commits = list(commits)
    youngest = commits[0]
    oldest = commits[0]

    if len(commits) == 1:
        return oldest, youngest

    if commit_date:
        for commit in commits[1:]:
            if repo[youngest].committer.date > repo[commit].committer.date:
                youngest = commit
            if repo[oldest].committer.date < repo[commit].committer.date:
                oldest = commit
    else:
        for commit in commits[1:]:
            if repo[youngest].author.date > repo[commit].author.date:
                youngest = commit
            if repo[oldest].author.date < repo[commit].author.date:
                oldest = commit

    return oldest, youngest


def upstream_duration_of_group(group):
    def ymd(dt):
        return dt.strftime('%Y-%m-%d')

    untagged, tagged = group

    # get youngest mail and youngest upstream commit
    oldest_mail, youngest_mail = get_youngest(repo, untagged, False)
    _, youngest_upstream = get_youngest(repo, tagged, True)

    oldest_mail_date = repo[oldest_mail].author.date
    youngest_mail_date = repo[youngest_mail].author.date

    youngest_upstream_date = repo[youngest_upstream].committer.date

    delta = youngest_upstream_date - youngest_mail_date

    delta = delta.days

    return youngest_upstream, ymd(youngest_mail_date), ymd(oldest_mail_date), \
           ymd(youngest_upstream_date), len(untagged), len(tagged), delta


def upstream_duration(config, argv):
    parser = argparse.ArgumentParser(prog='upstream_duration',
                                     description='upstream_time')

    args = parser.parse_args(argv)
    global repo
    repo = config.repo

    _, cluster = config.load_cluster()

    if config.mode == Config.Mode.MBOX:
        config.load_ccache_mbox()
    else:
        config.load_ccache_stack()

    log.info('Starting evaluation.')
    pool = Pool(cpu_count())
    tagged_only = [(d, u) for d, u in cluster.iter_split() if len(u) and len(d)]
    result = list(tqdm(pool.imap(upstream_duration_of_group, tagged_only), total=len(tagged_only)))
    pool.close()
    pool.join()
    log.info('  ↪ done.')

    # sort by upstream duration
    result.sort(key = lambda x: x[3])

    # save raw results
    with open(config.f_upstream_duration, 'w') as f:
        f.write('rep first_submission last_submission integration num_equiv num_up dur\n')
        for line in result:
            f.write('%s %s %s %s %d %d %d\n' % line)
