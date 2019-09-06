"""
PaStA - Patch Stack Analysis

Copyright (c) BMW Cat It, 2019

Author:
  Sebastian Duda <sebastian.duda@fau.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import datetime
from logging import getLogger
import math
import matplotlib.colors as nrm
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import pickle
import re
import sys
from tqdm import tqdm
import tikzplotlib

log = getLogger(__name__[-15:])

d_resources = './resources/linux/resources/'
f_prefix = 'eval_'
f_suffix = '.pkl'

patch_data = None
author_data = None
corr = []
show = True


def plot_total_rejected_ignored(data, x, ax):
    data.plot(x=x, y='total', ax=ax)
    data.plot(x=x, y='rejected', ax=ax)
    data.plot(x=x, y='ignored', ax=ax)


def corr_rejected_ignored(data):
    tmp1 = data.corr('pearson')
    corr.append({
        'tot_rej': tmp1['total']['rejected'],
        'tot_ign': tmp1['total']['ignored'],
        'rej_ign': tmp1['rejected']['ignored']
    })


def plot_and_corr(data, x, ax, from_index=False):
    global corr

    if from_index:
        data = data.reset_index()
    plot_total_rejected_ignored(data, x, ax)
    corr_rejected_ignored(data)


def display_and_save_plot(name):
    global show
    ax = plt.gca()

    plt.savefig('plots/' + name + '.svg')
    plt.savefig('plots/' + name + '.png', dpi=600)
    #tikzplotlib.save('plots' + name + ".tex")
    if show:
        plt.show()
    log.info('Plotted ' + name)


def normalize(data, max, args, by):
    factor = max / data[by]
    for item in args:
        data[item] = data[item] * factor
    return data


def p_by_rc():
    data = []
    for i in range(0, 11):
        data.append({'rc': i, 'total': 0, 'rejected': 0, 'ignored': 0})

    grp = patch_data.groupby(['rcv'])
    total = grp.count()['id']

    data = pd.DataFrame()
    data['kvs'] = patch_data[['rcv', 'kernel version']].groupby(['rcv']).nunique()['kernel version']
    data['total'] = total
    data['rejected'] = total - grp.sum()['upstream']
    data['ignored'] = grp.sum()['ignored']
    data.sort_index(inplace=True)
    data.reset_index(inplace=True)

    # Normalize odd rcvs
    data = data.apply(normalize, axis=1, args=(data['kvs'].max(), ['total', 'rejected', 'ignored', 'kvs'], 'kvs'))

    ax = plt.gca()
    ax.set_yscale('log')

    plot_total_rejected_ignored(data, 'rcv', ax)
    display_and_save_plot('by_rc')

    data['rejected/total'] = data['rejected'] / data['total']
    data['ignored/total'] = data['ignored'] / data['total']

    data.plot(x='rcv', y='rejected/total')
    display_and_save_plot('by_rc_r_ratio')

    data.plot(x='rcv', y='ignored/total')
    display_and_save_plot('by_rc_i_ratio')


def p_by_rc_v():
    ax = plt.gca()
    ax.set_yscale('log')

    g = patch_data.groupby(['kernel version', 'rcv'])
    d1 = g.sum()
    d2 = g.count()

    total = d2['id']
    rejected = total - d1['upstream']
    ignored = d1['ignored']

    series = {'total': total, 'rejected': rejected, 'ignored': ignored}
    frame = pd.DataFrame(series)
    frame.groupby(['kernel version']).apply(lambda x: plot_and_corr(x, 'rcv', ax, from_index=True))

    frame.reset_index(inplace=True)
    frame.sort_values(['rcv'], inplace=True)

    # frame['rejected/total'] = frame['rejected'] / frame['total']
    # frame.boxplot(by='rcv', column='rejected/total')
    # display_and_save_plot('by_rc_r_box')

    frame['ignored/total'] = frame['ignored'] / frame['total']
    ax = frame.boxplot(by='rcv', column='ignored/total')
    ax.set_xticklabels(
        ['MW', 'rc1..', 'rc2..', 'rc3..', 'rc4..', 'rc5..', 'rc6..', 'rc7..', 'rc8..', 'rc9..', 'rc10..'])
    #ax.set_ylabel('Ratio Ignored/Total')
    ax.set_title('')
    ax.get_figure().suptitle('')
    display_and_save_plot('by_rc_i_box')
    am = 0
    am = frame['ignored/total'].mean()
    print('AM: ' + str(am))

    # global corr
    # ax.set_yscale('linear')
    # corr = pd.DataFrame(corr)
    # corr.boxplot()
    # display_and_save_plot('by_rc_v_bp')


def _smooth(data, column, x):
    for i in range(0, len(data.index)):
        avg = data[column].iloc[i]
        count = 1
        for j in range(1, x + 1):
            if i + j < len(data.index):
                avg += data[column].iloc[i + j]
                count += 1
            elif i - j > 0:
                avg += data[column].iloc[i - j]
                count += 1
        data[column].iloc[i] = avg / count


def p_by_time():
    global patch_data
    day = patch_data['time'].apply(lambda x: datetime.datetime(year=x.year, month=x.month, day=x.day))
    patch_data['week'] = day - pd.to_timedelta(day.dt.dayofweek, unit='d')

    #patch_data = patch_data[patch_data['day'].apply(lambda x: x > patch_data['day'].min() and x < patch_data['day'].max())]

    grouped = patch_data.groupby(['week'])
    total = grouped.count()['id']
    rejected = total - grouped.sum()['upstream']
    ignored = grouped.sum()['ignored']

    result_frame = pd.DataFrame()
    result_frame['total'] = total
    result_frame['rejected'] = rejected
    result_frame['ignored'] = ignored
    result_frame.reset_index(inplace=True)

    ax = plt.gca()
    ax.set_yscale('log')
    ax.set_xlabel('')
    ax.set_ylabel('patches per week')
    result_frame.plot.line(x='week', y=['total', 'ignored'], ax=ax)
    display_and_save_plot('by_time')

    print(result_frame.corr())

    # Plot Scatterplot with regression line Ignored
    ax = plt.gca()
    result_frame.plot.scatter(x='total', y='ignored', ax=ax)

    fit_fn = np.poly1d(np.polyfit(result_frame['total'], result_frame['ignored'], 1))
    result_frame['reg_ign'] = result_frame['total'].apply(lambda x: fit_fn(x))
    result_frame.plot(x='total', y='reg_ign', ax=ax)

    ax.legend().remove()
    display_and_save_plot('by_time_ign_scat')
    print('regression of ignored/total (scat): ' + str(fit_fn))

    # Plot Scatterplot with regression line Rejected
    ax = plt.gca()
    result_frame.plot.scatter(x='total', y='rejected', ax=ax)

    fit_fn = np.poly1d(np.polyfit(result_frame['total'], result_frame['rejected'], 1))
    result_frame['reg_rej'] = result_frame['total'].apply(lambda x: fit_fn(x))
    result_frame.plot(x='total', y='reg_rej', ax=ax)

    display_and_save_plot('by_time_rej_scat')

    tmp = result_frame.corr('pearson')
    print('Total/Rejected: ' + str(tmp['total']['rejected']))
    print('Total/Ignored: ' + str(tmp['total']['ignored']))
    print('Rejected/Ignored: ' + str(tmp['rejected']['ignored']))

    result_frame = pd.DataFrame()
    result_frame['ignored/total'] = ignored / total
    result_frame.reset_index(inplace=True)
    _smooth(result_frame, 'ignored/total', 3)

    fit_fn = np.poly1d(np.polyfit(result_frame.index, result_frame['ignored/total'], 1))
    result_frame['index'] = pd.Series(result_frame.index)
    result_frame['regression'] = result_frame['index'].apply(lambda x: fit_fn(x))

    ax = result_frame.plot.line(x='week', y=['ignored/total', 'regression'])

    display_and_save_plot('by_time_ratio_ign')
    print('regression of ignored/total (line): ' + str(fit_fn))


    print(result_frame.corr())
    # result_frame['rejected/total'] = rejected/total
    # _smooth(result_frame, 'rejected/total', 3)

    # result_frame.plot.line()
    # display_and_save_plot('by_time_ratio')
    pass


def _plot_groups_old(data):
    group = data['group'][0]
    data['from'] = data['from'].apply(lambda x: 2 * math.sqrt(x) + 10)

    data.plot.scatter(x='total', y='rejected', s=data['from'])
    display_and_save_plot('total_rej_abs_' + str(group))

    data.plot.scatter(x='total', y='r_ratio', s=data['from'])
    display_and_save_plot('total_rej_rel_' + str(group))

    data.plot.scatter(x='total', y='ignored', s=data['from'])
    display_and_save_plot('total_ign_abs_' + str(group))

    data.plot.scatter(x='total', y='i_ratio', s=data['from'])
    display_and_save_plot('total_ign_rel_' + str(group))

    return data


def _plot_groups(data, dim, y_label=None, group=None, plot_label=None):
    if not group:
        group = data['group'][data.index[0]]
    cmap = plt.get_cmap('jet').reversed()
    norm = nrm.LogNorm(vmin=1, vmax=data['from'].max())

    ax = data.plot.scatter(x='total', y=dim, c='from', colormap=cmap, norm=norm, s=1)
    if y_label:
        ax.set_ylabel(y_label)

    if plot_label:
        ax.set_title(plot_label)

    display_and_save_plot('total_' + dim + str(group))


borders = [100, 4000]


def a_total_rej_ign():
    global author_data
    authors = []
    for author, data in author_data.items():
        tot = 0
        ups = 0
        ign = 0

        for patch in data:
            tot += 1
            if patch['ignored']:
                ign += 1
            if patch['upstream']:
                ups += 1

        authors.append({
            'from': author,
            'total': tot,
            'ignored': ign,
            'i_ratio': ign / tot,
            'rejected': tot - ups,
            'r_ratio': (tot - ups) / tot
        })

        if tot >= borders[1] or ign > 200:
            print('Author ' + author + ' has ' + str(tot) + ' totals, ' + str(tot - ups) + ' rejected, and ' + str(
                ign) + ' ignored patches.')

    authors = pd.DataFrame(authors)
    r_data = authors[['total', 'rejected', 'r_ratio', 'from']].groupby(
        ['total', 'rejected', 'r_ratio']).count().reset_index()
    i_data = authors[['total', 'ignored', 'i_ratio', 'from']].groupby(
        ['total', 'ignored', 'i_ratio']).count().reset_index()
    r_data['group'] = r_data['total'].apply(lambda x: 0 if x < borders[0] else 1 if x < borders[1] else 2)
    i_data['group'] = i_data['total'].apply(lambda x: 0 if x < borders[0] else 1 if x < borders[1] else 2)

    p_groups = r_data.groupby(by=['group'])
    r_groups = dict()
    for group, data in p_groups:
        r_groups[group] = data

    p_groups = i_data.groupby(by=['group'])
    i_groups = dict()
    for group, data in p_groups:
        i_groups[group] = data

    _plot_groups(r_groups[0], 'rejected', 'rejected', 0)
    _plot_groups(r_groups[0], 'r_ratio', 'ratio rejected/total', 0)

    _plot_groups(i_groups[0], 'ignored', 'ignored', 0)
    _plot_groups(i_groups[0], 'i_ratio', 'ratio ignored/total', 0)

    _plot_groups(pd.concat([r_groups[0], r_groups[1]]), 'rejected', 'rejected', '0-1')
    _plot_groups(pd.concat([r_groups[0], r_groups[1]]), 'r_ratio', 'ratio rejected/total', '0-1')

    _plot_groups(pd.concat([i_groups[0], i_groups[1]]), 'ignored', 'ignored', '0-1')
    _plot_groups(pd.concat([i_groups[0], i_groups[1]]), 'i_ratio', 'ratio ignored/total', '0-1')

    print('regression of rejected: ' + str(np.poly1d(np.polyfit(r_data['total'], r_data['rejected'], 1))))
    print('regression of rejected ratio: ' + str(np.poly1d(np.polyfit(r_data['total'], r_data['r_ratio'], 1))))
    print('regression of ignored: ' + str(np.poly1d(np.polyfit(i_data['total'], i_data['ignored'], 1))))
    print('regression of ignored ratio: ' + str(np.poly1d(np.polyfit(i_data['total'], i_data['i_ratio'], 1))))


def build_data():
    print(' building…')
    global author_data

    author_data = dict()

    for index, tline in patch_data.iterrows():
        line = tline.to_dict()
        email = line['from'][1]
        if email not in author_data:
            author_data[email] = list()

        author_data[email].append(line)


def analysis_patches(config, prog, argv):
    global author_data
    global patch_data

    _, clustering = config.load_cluster()
    clustering.optimize()

    log.info('Loading Data')

    load = pickle.load(open(d_resources + 'eval_characteristics.pkl', 'rb'))

    relevant = {m for m, c in load.items() if
                    c.is_patch and
                    c.patches_linux and
                    c.is_first_patch_in_thread and
                    not c.is_stable_review and
                    not c.is_next and
                    not c.process_mail and
                    not c.is_from_bot}
    irrelevant = load.keys() - relevant

    ignored_single = {m for m in relevant if
                        not load[m].is_upstream and
                        not load[m].has_foreign_response}

    ignored_related = {patch for patch in ignored_single
                        if False not in [load[x].has_foreign_response == False
                                          for x in (clustering.get_downstream(patch) & relevant)]}

    data = []
    for patch in relevant:
        character = load[patch]
        tag = character.linux_version.split('-rc')
        kv = [int(x) for x in tag[0][1:].split('.')]

        if len(tag) == 1: # we have a release
            # Set rc to 0 and shift it to the next MW
            rc = 0
            kv[-1] += 1
        else:
            rc = int(tag[1])
        kv = 'v' + '.'.join([str(v) for v in kv])

        ignored = int(patch in ignored_related)
        upstream = int(character.is_upstream)

        data.append({
            'id': patch,
            'from': character.mail_from,
            'kernel version': kv,
            'rcv': rc,
            'upstream': upstream,
            'ignored': ignored,
            'time': character.date
        })
    log.info('There are ' + str(len(irrelevant)) + ' irrelevant Mails.')
    patch_data = pd.DataFrame(data)

    # Clean Data
    # remove v2.* and v5.*
    patch_data.set_index('kernel version', inplace=True)
    patch_data = patch_data.filter(regex='^v[^25].*', axis=0)
    patch_data.reset_index(inplace=True)
    # Remove outlier
    pre_outlier = len(patch_data.index)
    '''
    patch_data = patch_data[patch_data['from'].apply(lambda x: not x in [
        # Total > 3500
        ('arnaldo carvalho de melo', 'acme@kernel.org'),
        ('jeff kirsher', 'jeffrey.t.kirsher@intel.com'),
        ('simon horman', 'horms+renesas@verge.net.au'),
        ('christoph hellwig', 'hch@lst.de'),
        ('marc zyngier', 'marc.zyngier@arm.com'),
        ('arnd bergmann', 'arnd@arndb.de'), # + rejected
        # Ignored > 200
        ('baole ni', 'baolex.ni@intel.com'),
        ('rickard strandqvist', 'rickard_strandqvist@spectrumdigital.se'),
        # Total + Rejected + Ignored
        ('sf markus elfring', 'elfring@users.sourceforge.net'),
        ('mark brown', 'broonie@kernel.org')
    ])]
    '''
    #patch_data = patch_data[patch_data['time'].apply(lambda x: x.year >= 2018)]

    post_outlier = len(patch_data.index)
    log.info(str(pre_outlier - post_outlier) + ' Patches were removed. (Outlier)')
    log.info(str(post_outlier) + ' Patches remain.')

    if os.path.isfile(d_resources + 'other_data.pkl'):
        author_data = pickle.load(open(d_resources + 'other_data.pkl', 'rb'))
    else:
        build_data()
        pickle.dump(author_data, open(d_resources + 'other_data.pkl', 'wb'))

    log.info(' → Done')

    plt.rc('font', size=15)

    #p_by_rc()
    p_by_rc_v()
    #p_by_time()
    #a_total_rej_ign()
