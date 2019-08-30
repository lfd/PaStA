#!/usr/bin/python3
import os
import datetime
import math
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pickle
import sys

patch_data = None
author_data = None
subsystem_data = None
corr = []
show = True
size = 'small'


def plot_total_rejected_ignored(data, x, ax):
    data.plot(x=x, y='total', ax=ax)
    data.plot(x=x, y='rejected', ax=ax)
    data.plot(x=x, y='ignored', ax=ax)


def corr_rejected_ignored (data):
    tmp1 = data.corr('pearson')
    corr.append({
        'tot_rej': tmp1['total']['rejected'],
        'tot_ign': tmp1['total']['ignored'],
        'rej_ign': tmp1['rejected']['ignored']
    })


def plot_and_corr (data, x, ax, from_index=False):
    global corr

    if from_index:
        data = data.reset_index()
    plot_total_rejected_ignored(data, x, ax)
    corr_rejected_ignored(data)


def display_and_save_plot(name):
    global show
    plt.savefig('plots/' + name + '.svg')
    plt.savefig('plots/' + name + '.png', dpi=600)
    if show:
        plt.show()


def normalize (data, max, args, by):
    factor = max / data[by]
    for item in args:
        data[item] = data[item] * factor
    return data


def p_by_rc ():
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

    data['rejected/total'] = data['rejected']/data['total']
    data['ignored/total'] = data['ignored']/data['total']

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

    frame['rejected/total'] = frame['rejected'] / frame['total']
    frame.boxplot(by='rcv', column='rejected/total')
    display_and_save_plot('by_rc_r_box')

    frame['ignored/total'] = frame['ignored'] / frame['total']
    frame.boxplot(by='rcv', column='ignored/total')
    display_and_save_plot('by_rc_r_box')

    global corr
    ax.set_yscale('linear')
    corr = pd.DataFrame(corr)
    corr.boxplot()
    display_and_save_plot('by_rc_v_bp')


def _smooth(data, column, x):
    for i in range(0, len(data.index)):
        avg = data[column].iloc[i]
        count = 1
        for j in range(1, x+1):
            if i+j < len(data.index):
                avg += data[column].iloc[i+j]
                count += 1
            elif i-j > 0:
                avg += data[column].iloc[i-j]
                count += 1
        data[column].iloc[i] = avg/count


def p_by_time ():
    global patch_data
    day = patch_data['timestamp'].apply(lambda x: datetime.datetime.utcfromtimestamp(x - x % (604800)))
    patch_data['day']  = day

    grouped = patch_data.groupby(['day'])
    total = grouped.count()['id']
    rejected = total - grouped.sum()['upstream']
    ignored = grouped.sum()['ignored']

    result_frame = pd.DataFrame()
    result_frame['total'] = total
    result_frame['rejected'] = rejected
    result_frame['ignored'] = ignored

    ax = plt.gca()
    ax.set_yscale('log')
    result_frame.plot.line(ax=ax)
    display_and_save_plot('by_time')

    # Plot Scatterplot with regression line Ignored
    ax = plt.gca()
    result_frame.plot.scatter(x='total', y='ignored', ax=ax)

    fit_fn = np.poly1d(np.polyfit(result_frame['total'], result_frame['ignored'],1))
    result_frame['reg_ign'] = result_frame['total'].apply(lambda x: fit_fn(x))
    result_frame.plot(x='total', y='reg_ign', ax=ax)

    display_and_save_plot('by_time_ign_scat')

    # Plot Scatterplot with regression line Rejected
    ax = plt.gca()
    result_frame.plot.scatter(x='total', y='rejected', ax=ax)

    fit_fn = np.poly1d(np.polyfit(result_frame['total'], result_frame['rejected'],1))
    result_frame['reg_rej'] = result_frame['total'].apply(lambda x: fit_fn(x))
    result_frame.plot(x='total', y='reg_rej', ax=ax)

    display_and_save_plot('by_time_rej_scat')

    tmp = result_frame.corr('pearson')
    print('Total/Rejected: ' +  str(tmp['total']['rejected']))
    print('Total/Ignored: ' +  str(tmp['total']['ignored']))
    print('Rejected/Ignored: ' +  str(tmp['rejected']['ignored']))

    result_frame = pd.DataFrame()
    result_frame['ignored/total'] = ignored/total
    _smooth(result_frame, 'ignored/total', 3)

    result_frame.plot.line()
    display_and_save_plot('by_time_ratio_ign')

    result_frame['rejected/total'] = rejected/total
    _smooth(result_frame, 'rejected/total', 3)

    result_frame.plot.line()
    display_and_save_plot('by_time_ratio')
    pass


def _plot_groups(data):
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
            'i_ratio': ign/tot,
            'rejected': tot - ups,
            'r_ratio': (tot - ups)/tot
        })

    authors = pd.DataFrame(authors)
    data = authors.groupby(['total', 'rejected', 'r_ratio', 'ignored', 'i_ratio']).count()
    data.reset_index(inplace=True)
    data['group'] = data['total'].apply(lambda x: 0 if x < 250 else 1 if x < 4000 else 2)

    groups = data.groupby(['group'])
    groups.apply(_plot_groups)


def build_data():
    print(' building…')
    global author_data
    global subsystem_data

    author_data = dict()
    subsystem_data = dict()

    for index, tline in patch_data.iterrows():
        line = tline.to_dict()
        try:
            author_data[line['from']].append(line)
        except KeyError:
            author_data[line['from']] = [line]
        if line['subsystems'] is None:
            continue
        for subsystem in line['subsystems']:
            try:
                subsystem_data[subsystem].append(line)
            except KeyError:
                subsystem_data[subsystem] = [line]


if __name__ == '__main__':
    print('Loading Patches… ' + size)
    load = pickle.load(open('eval_characteristics.pkl','rb'))

    if False:
        data = []
        for patch, character in load.items():

            data.append({
                'id': patch
            })
        patch_data = pd.DataFrame(data)
    else:
        try:
            patch_data = pd.DataFrame(pickle.load(open('patch_data_' + size + '.pkl', 'rb')))
        except FileNotFoundError:
            print('Patch Data file does not exist', file=sys.stderr)
            sys.exit(-1)

    # Clean Data
    # remove v2.* and v5.*
    patch_data.set_index('kernel version', inplace=True)
    patch_data = patch_data.filter(regex='^v[^25].*', axis=0)
    patch_data.reset_index(inplace=True)
    # Remove process mails
    patch_data = patch_data[patch_data['process_mail'].apply(lambda x: not x)]
    # Remove Baole
    patch_data = patch_data[patch_data['from'].apply(lambda x: x != 'Baole Ni <baolex.ni@intel.com>')]
    # Bool to int
    patch_data = patch_data.replace(True, 1)
    # rcv as int
    patch_data['rcv'] = patch_data['rcv'].apply((lambda x: int(x)))
    print(' → Done')

    print(patch_data.describe())

    print('Loading Other Data…')
    if os.path.isfile('other_data_' + size + '.pkl'):
        author_data, subsystem_data = pickle.load(open('other_data_' + size + '.pkl', 'rb'))
    else:
        build_data()
        pickle.dump((author_data, subsystem_data), open('other_data_' + size + '.pkl', 'wb'))

    print(' → Done')

    #p_by_rc()
    p_by_rc_v()
    #p_by_time()

    #a_total_rej_ign()