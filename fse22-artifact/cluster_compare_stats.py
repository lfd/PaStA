#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2026

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import argparse
import csv
import os
import statistics
import sys

from datetime import datetime, timezone
from multiprocessing import Pool
from sklearn import metrics

import pygit2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import Clustering
from pypasta.Config import Config

LATEX_NAMES = {
    'linux':  r'\linux',
    'qemu':   r'\qemu',
    'u-boot': r'\uboot',
    'xen':    r'\xen',
}

CLUSTER_DIRS = [
    'maintainers_cluster',
    'maintainers_cluster_fast_greedy',
    'maintainers_cluster_infomap',
    'maintainers_cluster_louvain',
]


def version_key(filename):
    stem = filename[:-4].lstrip('v')  # strip .csv and leading 'v'
    return [int(x) for x in stem.replace('-', '.').split('.') if x.isdigit()]


def resolve_tag(repo, tag):
    obj = repo.get(repo.lookup_reference('refs/tags/' + tag).target)
    if isinstance(obj, pygit2.Tag):
        return obj.tagger.time, repo.get(obj.target)
    return obj.committer.time, obj


def tag_date(repo, tag):
    ts, _ = resolve_tag(repo, tag)
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def maintainer_count(repo, tag):
    _, commit = resolve_tag(repo, tag)
    blob = commit.tree['MAINTAINERS']
    lines = blob.data.decode('utf-8', errors='replace').splitlines()
    return len(set(l[2:].strip() for l in lines if l.startswith('M:')))


def kloc(filemap_path):
    total = 0
    with open(filemap_path) as f:
        for row in csv.DictReader(f):
            total += int(row['lines'])
    return total // 1000


def sections_clusters(cluster_csv_path):
    reps = set()
    rows = 0
    with open(cluster_csv_path) as f:
        for row in csv.DictReader(f):
            reps.add(row['c_representative'])
            rows += 1
    return rows, len(reps)


def latex_row(project, res, versions, results_by_dir):
    repo = pygit2.Repository(os.path.join('resources', project, 'repo'))

    v0 = versions[0][:-4]   # strip .csv
    v1 = versions[-1][:-4]

    date0 = tag_date(repo, v0)
    date1 = tag_date(repo, v1)
    years = round((date1 - date0).days / 365)

    mtrs0 = maintainer_count(repo, v0)
    mtrs1 = maintainer_count(repo, v1)

    graph_dir = os.path.join(res, 'maintainers_section_graph')
    kloc0 = kloc(os.path.join(graph_dir, v0 + '_filemap.csv'))
    kloc1 = kloc(os.path.join(graph_dir, v1 + '_filemap.csv'))

    wt_dir = os.path.join(res, 'maintainers_cluster')
    sec0, clu0 = sections_clusters(os.path.join(wt_dir, versions[0]))
    sec1, clu1 = sections_clusters(os.path.join(wt_dir, versions[-1]))

    def pv(cluster_dir):
        _, pur_vals, vm_vals = results_by_dir[cluster_dir]
        return statistics.mean(pur_vals), statistics.mean(vm_vals)

    lp, lv = pv('maintainers_cluster_louvain')
    ip, iv = pv('maintainers_cluster_infomap')
    fp, fv = pv('maintainers_cluster_fast_greedy')

    name = LATEX_NAMES.get(project, project)

    return (
        f'{name} & {years} years'
        f' & {mtrs0} & {mtrs1}'
        f' & {kloc0} & {kloc1}'
        f' & {sec0} ({clu0}) & {sec1} ({clu1})'
        f' & {lp*100:.1f}\\% & {lv*100:.1f}\\%'
        f' & {ip*100:.1f}\\% & {iv*100:.1f}\\%'
        f' & {fp*100:.1f}\\% & {fv*100:.1f}\\%\\\\'
        f' % {v0} -- {v1}'
    )


def csv_to_clustering(csv_path):
    clustering = Clustering()
    clusters = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            clusters.setdefault(row['c_representative'], set()).add(row['c_section'])
    for members in clusters.values():
        clustering.insert(*members)
    return clustering


def purity(ground_truth, prediction):
    hits = 0
    for cluster in ground_truth:
        best = 0
        for element in cluster:
            overlap = len(cluster & prediction[element])
            if overlap > best:
                best = overlap
        hits += best
    return hits / len(ground_truth.get_all_elements())


def compare(ground_truth, prediction):
    gt_keys = ground_truth.get_all_elements()
    pred_keys = prediction.get_all_elements()

    for elem in gt_keys - pred_keys:
        prediction.insert_element(elem)
    for elem in pred_keys - gt_keys:
        ground_truth.insert_element(elem)

    gt = [v for _, v in sorted(ground_truth.lookup.items())]
    t  = [v for _, v in sorted(prediction.lookup.items())]

    _, _, vm = metrics.homogeneity_completeness_v_measure(gt, t)
    fm  = metrics.fowlkes_mallows_score(gt, t)
    pur = purity(ground_truth, prediction)

    return fm, pur, vm


def process_cluster_dir(args):
    wt_dir, other_dir, cluster_dir, versions = args
    print(f'Comparing walktrap against {cluster_dir}...', flush=True)
    fm_vals, pur_vals, vm_vals = [], [], []

    for version in versions:
        other_path = os.path.join(other_dir, version)
        if not os.path.exists(other_path):
            continue

        ground_truth = csv_to_clustering(os.path.join(wt_dir, version))
        prediction   = csv_to_clustering(other_path)
        fm, pur, vm  = compare(ground_truth, prediction)
        fm_vals.append(fm)
        pur_vals.append(pur)
        vm_vals.append(vm)

    return cluster_dir, fm_vals, pur_vals, vm_vals


def process_project(project):
    print(f'=== Project: {project} ===')
    config = Config(project)
    t0 = config.upstream_range.split('..')[0]

    res    = os.path.join('resources', project, 'resources')
    wt_dir = os.path.join(res, 'maintainers_cluster')
    versions = sorted(
        (f for f in os.listdir(wt_dir)
         if f.endswith('.csv') and '-rc' not in f
         and version_key(f) >= version_key(t0 + '.csv')),
        key=version_key,
    )

    repo = pygit2.Repository(os.path.join('resources', project, 'repo'))
    v0, v1 = versions[0][:-4], versions[-1][:-4]
    date0, date1 = tag_date(repo, v0), tag_date(repo, v1)
    years = round((date1 - date0).days / 365)
    graph_dir = os.path.join(res, 'maintainers_section_graph')
    print(f'  {v0} → {v1}  ({years} years)')
    print(f'  #Mtrs:    {maintainer_count(repo, v0)} → {maintainer_count(repo, v1)}')
    print(f'  kLoC:     {kloc(os.path.join(graph_dir, v0 + "_filemap.csv"))} → {kloc(os.path.join(graph_dir, v1 + "_filemap.csv"))}')
    sec0, clu0 = sections_clusters(os.path.join(wt_dir, versions[0]))
    sec1, clu1 = sections_clusters(os.path.join(wt_dir, versions[-1]))
    print(f'  Sections: {sec0} ({clu0}) → {sec1} ({clu1})')
    print()

    pool_args = [
        (wt_dir, os.path.join(res, d), d, versions)
        for d in CLUSTER_DIRS
    ]

    with Pool(len(CLUSTER_DIRS)) as pool:
        results = pool.map(process_cluster_dir, pool_args)

    results_by_dir = {d: (fm, pur, vm) for d, fm, pur, vm in results}

    for cluster_dir, fm_vals, pur_vals, vm_vals in results:
        print(f'  {cluster_dir}')
        for name, vals in [('Fowlkes-Mallows', fm_vals),
                           ('Purity',          pur_vals),
                           ('V-Measure',       vm_vals)]:
            print(f'    {name}: mean={statistics.mean(vals):.3f}  median={statistics.median(vals):.3f}')
    print()

    return latex_row(project, res, versions, results_by_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('projects', nargs='*', help='Project names (default: read from config)')
    args = parser.parse_args()

    if args.projects:
        projects = args.projects
    else:
        with open('config') as f:
            projects = [f.read().strip()]

    rows = [process_project(p) for p in projects]

    print(r'\begin{tabular}{l r rr rr rr cc cc cc}')
    print(r'\toprule')
    print(r' & \multicolumn{1}{c}{$t_1-t_0$} & \multicolumn{2}{c}{\#Mtrs} & \multicolumn{2}{c}{kLoC} & \multicolumn{2}{c}{Sections (Clusters)}')
    print(r' & \multicolumn{2}{c}{Louvain} & \multicolumn{2}{c}{Infomap} & \multicolumn{2}{c}{Fastgreedy} \\')
    print(r'\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}')
    print(r'\cmidrule(lr){9-10}\cmidrule(lr){11-12}\cmidrule(lr){13-14}')
    print(r'Project & & $t_0$ & $t_1$ & $t_0$ & $t_1$ & $t_0$ & $t_1$ & P & V & P & V & P & V \\')
    print(r'\midrule')
    for row in rows:
        print(row)
    print(r'\bottomrule')
    print(r'\end{tabular}')


if __name__ == '__main__':
    main()
