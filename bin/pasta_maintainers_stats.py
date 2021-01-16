"""
PaStA - Patch Stack Analysis

Copyright (c) Bayerische Motoren Werke Aktiengesellschaft (BMW AG), 2020
Copyright (c) OTH Regensburg, 2020

Authors:
   Basak Erdamar <basakerdamar@gmail.com>
   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import networkx as nx
import os
import pygit2
import sys

from argparse import ArgumentParser
from collections import defaultdict, Counter
from csv import writer
from itertools import combinations
from logging import getLogger
from multiprocessing import Pool, cpu_count

sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from pypasta.LinuxMaintainers import LinuxMaintainers
from pypasta.Util import file_to_string

log = getLogger(__name__[-15:])

# We need this global variable, as pygit2 Commit.tree objects are not pickleable
_tmp_tree = None
_all_maintainers = None


def walk_commit_tree(tree):
    results = set()

    for entry in tree:
        if type(entry) == pygit2.Blob:
            results.add(entry.name)
        elif type(entry) == pygit2.Tree:
            results |= {os.path.join(entry.name, item)
                        for item in walk_commit_tree(entry)}
        else:
            raise TypeError('Unknown type: %s' % type(entry))

    return results


def get_file_infos(filename):
    blob = _tmp_tree[filename]
    lines = blob.data.count(b'\n')
    size = blob.size

    sections = _all_maintainers.get_sections_by_file(filename)

    return filename, (lines, size, sections)


def pretty_name(maintainer):
    return maintainer[0]+' <'+maintainer[1]+'>'


def get_status(all_maintainers, section_name):
    if any(all_maintainers.sections[section_name].status):
        return all_maintainers.sections[section_name].status[0].value
    else:
        return ''


def dump_csv(headers, relevant_headers, data, f_csv, verbose):
    headers_pretty = '\t\t'.join([headers[x][0] for x in relevant_headers])
    if verbose:
        print(headers_pretty)
        for entry in data:
            str = ''
            for num in relevant_headers:
                str += headers[num][1] % entry[num] + '\t\t'
            if verbose:
                print(str)

    with open(f_csv, 'w+') as csv_file:
        csv_writer = writer(csv_file)
        csv_writer.writerow([h[2] for h in headers])
        csv_writer.writerows(data)


# generate_graph generates an edge list for an undirected graph that represents
# the overlapping code that is covered by the MAINTAINERS file. Every node of
# the graph represents a section in MAINTAINERS. A section node has an edge to
# another section node if both sections share at least one file. An edge weighted
# by the LoC/size in bytes of the shared content.
def generate_graph(file_map, file_filters, f_csv):
    filenames = file_filters
    if not filenames:
        filenames = file_map.keys()

    G = nx.Graph()

    # Iterate over all filenames, determine their size/LoC and to what sections
    # they belong. Then, add the weight to connected sections
    for filename in filenames:
        lines, size, sections = file_map[filename]

        # Sum up the size of each section: Each section gets a self-loop that
        # represents the size of the node
        for section in sections:
            if not G.has_edge(section, section):
                G.add_edge(section, section, weight=Counter())
            G[section][section]['weight'].update(lines=lines, size=size)

        # Update edges to all other sections
        for c1, c2 in combinations(sections, 2):
            if not G.has_edge(c1, c2):
                G.add_edge(c1, c2, weight=Counter())
            G[c1][c2]['weight'].update(lines=lines, size=size)

    with open(f_csv, 'w') as csv_file:
        csv_writer = writer(csv_file)
        line = ["from", "to", "lines", "size"]
        csv_writer.writerow(line)

        for a, b in G.edges:
            ctr_edge = G[a][b]['weight']
            line = [a, b, ctr_edge['lines'], ctr_edge['size']]
            csv_writer.writerow(line)


def maintainers_stats(config, argv):
    parser = ArgumentParser(prog='maintainers_stats',
                            description='Display file sizes grouped by '
                                        'maintainers or sections')
    parser.add_argument('--smallstat', action='store_true', help='Simple view')
    parser.add_argument('--size', action='store_true',
                        help='Show sizes (in bytes)')
    parser.add_argument('--filter', type=str,
                        help='Only respect files named in FILTER. The first '
                             'line of FILTER must contain ther kernel version. '
                             'All files of the kernel version will be '
                             'considered if --filter is not specified.')
    parser.add_argument('--group-by', type=str, default='sections',
                        choices={'files', 'maintainers', 'sections'},
                        help='(only used in combination with --mode stats) '
                             'files: option shows all sections that are '
                             'assigned to the input files. '
                             'sections: option groups files by sections and '
                             'displays sections ordered by their size (LoC). '
                             'maintainers: option groups files by '
                             'maintainers and shows each maintainer '
                             'ordered by the LoC they are responsible for. '
                             'Default: %(default)s')
    parser.add_argument('--revision', type=str, help='Specify a commit hash or '
                        'a version name for a Linux repo')
    parser.add_argument('--mode', type=str, default='stats',
                        choices={'stats', 'graph'},
                        help='stats: dump stats to a csv-file. '
                             'graph: generate a csv-file that serves as a basis for a graph. '
                             'Default: %(default)s')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='Verbose mode.')

    args = parser.parse_args(argv)

    repo = config.repo

    kernel_revision = 'HEAD'
    filter_by_files = list()
    if args.filter:
        filter_by_files = file_to_string(args.filter).splitlines()
        # The first line of the file must contain a valid kernel version,
        # tag or commit hash
        kernel_revision = filter_by_files.pop(0)

    # arguments may override the kernel revision, if it is not already set
    if args.revision:
        kernel_revision = args.revision
    log.info('Working on kernel revision %s' % kernel_revision)

    all_maintainers = LinuxMaintainers(repo, kernel_revision)
    tree = repo.get_tree(kernel_revision)
    all_filenames = walk_commit_tree(tree)
    result = list()

    if args.group_by == 'files':
        filenames = filter_by_files if len(filter_by_files) else all_filenames

        headers = [('%-30s' % 'Filename', '%-30.30s', 'filename'),
                   ('Sections of file', '%-s', 'sections')]
        for filename in filenames:
            sections = all_maintainers.get_sections_by_file(filename)
            sections -= {'THE REST'}
            result.append((filename, ', '.join(sections)))

        dump_csv(headers, [0, 1], result, config.f_maintainers_stats, args.verbose)
        return

    # We end up here in case of args.group_by in {'sections', 'maintainers'}
    global _tmp_tree
    global _all_maintainers

    _tmp_tree = tree
    _all_maintainers = all_maintainers
    processes = int(cpu_count())
    p = Pool(processes=processes, maxtasksperchild=1)
    file_map = p.map(get_file_infos, all_filenames)
    p.close()
    p.join()

    _tmp_tree = None
    _all_maintainers = None

    file_map = dict(file_map)

    if args.mode == 'graph':
        generate_graph(file_map, filter_by_files, config.f_maintainers_section_graph)
        return

    # An object is the kind of the analysis, and reflects the target. A target
    # can either be a section or the maintainer.

    # Maps Section/Maintainer to a Counter
    object_stats = defaultdict(Counter)
    # Maps Section/Maintainer to a set of files
    object_files = defaultdict(set)

    relevant = defaultdict(Counter)

    #############################################
    # Routines that handle differences between
    # maintainer / section grouping
    #############################################
    # Routines that are chosen in case of --group-by maintainers
    def _evaluator_maintainers(file, lines, size, section):
        _, mtrs, _ = all_maintainers.get_maintainers(section)
        for mtr in mtrs:
            object_files[mtr].add(file)
            object_stats[mtr].update(lines=lines, size=size)

    def _filter_maintainers(section, lines, size):
        _, mtrs, _ = all_maintainers.get_maintainers(section)
        for mtr in mtrs:
            relevant[mtr].update(lines=lines, size=size)

    # Routines that are chosen in case of --group-by sections
    def _evaluator_sections(file, lines, size, section):
        object_files[section].add(file)
        object_stats[section].update(lines=lines, size=size)

    def _filter_sections(section, lines, size):
        relevant[section].update(lines=lines, size=size)
    #############################################

    # Choose the right routines
    _title, _evaluator, _filter = {
        'maintainers': ('Maintainers',
                        _evaluator_maintainers,
                        _filter_maintainers),

        'sections': ('Sections',
                     _evaluator_sections,
                     _filter_sections),
    }[args.group_by]

    # First of all, fill object_{stats, file}
    for file, (lines, size, sections) in file_map.items():
        for section in sections:
            _evaluator(file, lines, size, section)

    # Do we have to respect any filters?
    if len(filter_by_files):
        for file in filter_by_files:
            lines, size, sections = file_map[file]
            for section in sections:
                _filter(section, lines, size)
    else:
        # Everything is relevant, if there is no filter.
        relevant = object_stats

    # Fill all the format strings
    headers = [('%-30s' % _title, '%-30.30s', _title),
               ('Sum Lines', '%-9u', 'sum_lines'),
               ('File size', '%-14u', 'filesize'),
               ('Lines in filter', '%-10u', 'lines_in_filter'),
               ('Lines percentage', '%-16.2f', 'lines_percentage'),
               ('Relevant files', '%-s', 'relevant_files'),
               ('%-10s' % 'status', '%-10s', 'status')]

    for object, counter in relevant.items():
        object_stat = object_stats[object]
        lines_percentage = counter['lines'] / object_stat['lines']

        # 0: title
        item = (object if not args.group_by == 'maintainers' else pretty_name(object), )
        # 1: sum_lines
        item += (object_stat['lines'], )
        # 2: file_size
        item += (object_stat['size'], )
        # 3: loc_filter
        item += (counter['lines'], )
        # 4: loc_percentage
        item += (lines_percentage, )
        # 5: relevant_files
        item += (', '.join({filename for filename in object_files[object] if filename in filter_by_files}), )
        # 6: status
        if args.group_by == 'sections':
            item += (get_status(all_maintainers, object), )
        else:
            item += (None, )

        result.append(item)

    # sort by lines percentage
    result.sort(key=lambda x: x[3])

    # determine the order of the columns
    relevant_headers = [0, 1]
    if args.group_by == 'sections':
        relevant_headers.append(6)
    if args.size:
        relevant_headers.append(2)
    if filter_by_files:
        relevant_headers += [3, 4, 5]

    dump_csv(headers, relevant_headers, result, config.f_maintainers_stats, args.verbose)
