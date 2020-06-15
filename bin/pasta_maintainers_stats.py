"""
PaStA - Patch Stack Analysis

Copyright (c) Bayerische Motoren Werke Aktiengesellschaft (BMW AG), 2020
Copyright (c) OTH Regensburg, 2020

Authors:
  Basak Erdamar <basakerdamar@gmail.com>
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import os
import pygit2
import sys

from argparse import ArgumentParser
from collections import defaultdict, Counter
from csv import writer
from logging import getLogger
from multiprocessing import Pool, cpu_count

sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from pypasta.LinuxMaintainers import load_maintainer
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


def get_tree(repo, revision):
    if revision == 'HEAD':
        return repo.revparse_single(repo.head.name).tree

    if revision.startswith('v'):
        revision = repo.lookup_reference('refs/tags/%s' % revision).target
    commit_hash = repo[revision].target
    tree = repo[commit_hash].tree

    return tree


def get_file_map(filename):
    blob = _tmp_tree[filename]
    lines = blob.data.count(b'\n')
    size = blob.size

    sections = _all_maintainers.get_subsystems_by_file(filename)

    return filename, (lines, size, sections)


def pretty_name(maintainer):
    return maintainer[0]+' <'+maintainer[1]+'>'


def get_status(all_maintainers, section_name):
    if any(all_maintainers.subsystems[section_name].status):
        return all_maintainers.subsystems[section_name].status[0].value
    else:
        return ''


def dump_csv(title, data, filename):

    if filename:
        with open(filename, 'w+') as csv_file:
            csv_writer = writer(csv_file)
            csv_writer.writerow([header[0] for header in title])
            csv_writer.writerows(data)
        return

    # El Cheapo pretty printer.
    headers = '\t\t'.join([header[0] for header in title])
    formats = '\t\t'.join([header[1] for header in title])

    print(headers)
    for entry in data:
        print(formats % entry)


def maintainers_stats(config, sub, argv):
    parser = ArgumentParser(description='Display file sizes grouped by '
                                            'maintainers or sections')
    parser.add_argument('maintainers_stats', nargs=1, type=bool)
    parser.add_argument('--smallstat', action='store_true', help='Simple view')
    parser.add_argument('--bytes', action='store_true', help='Show byte counts')
    parser.add_argument('--outfile', type=str, help='Output to a csv file')
    parser.add_argument('--filter', type=str, help='Filter by file list: '
                        'enter the file name for the file containing the list '
                        'of files to filter by.')
    parser.add_argument('--group-by', type=str, default='sections',
                        choices={'maintainers', 'sections', 'files'},
                        help='files option '
                        'displays files with corresponding sections. '
                        'sections option groups files by sections, displays '
                        'sections ordered by lines of code they include. '
                        'maintainers option groups files by sections, displays '
                        'each maintainer ordered by lines of code they are '
                        'responsible for. '
                        'Default is sections if no value is specified')
    parser.add_argument('--revision', type=str, help='Specify a commit hash or '
                        'a version name for a Linux repo')

    args = parser.parse_args()
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

    all_maintainers = load_maintainer(repo, kernel_revision)
    tree = get_tree(repo.repo, kernel_revision)
    all_filenames = walk_commit_tree(tree)

    if args.group_by == 'files':
        filenames = filter_by_files if len(filter_by_files) else all_filenames

        title = [('%-30s' % 'Filename', '%-30.30s'),
                 ('Sections of file', '%-s')]
        results = []
        for filename in filenames:
            sections = all_maintainers.get_subsystems_by_file(filename)
            sections -= {'THE REST'}
            results.append((filename, ', '.join(sections)))

        dump_csv(title, results, args.outfile)
        return

    # We end up here in case of args.group_by in {'sections', 'maintainers'}
    global _tmp_tree
    global _all_maintainers

    _tmp_tree = tree
    _all_maintainers = all_maintainers
    processes = int(cpu_count())
    p = Pool(processes=processes, maxtasksperchild=1)
    file_map = p.map(get_file_map, all_filenames)
    p.close()
    p.join()

    _tmp_tree = None
    _all_maintainers = None

    file_map = dict(file_map)

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

    def _filter_sections(section, lines, size):
        relevant[section].update(lines=lines, size=size)

    # Routines that are chosen in case of --group-by sections
    def _evaluator_sections(file, lines, size, section):
        object_files[section].add(file)
        object_stats[section].update(lines=lines, size=size)

    def _filter_maintainers(section, lines, size):
        _, mtrs, _ = all_maintainers.get_maintainers(section)
        for mtr in mtrs:
            relevant[mtr].update(lines=lines, size=size)
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
    for file in filter_by_files:
        lines, size, sections = file_map[file]
        for section in sections:
            _filter(section, lines, size)

    # Fill the first two fields of the title
    title = [('%-30s' % _title, '%-30.30s'),
             ('Sum Lines', '%-9u')]

    if args.bytes:
        title += [('File size',   '%-15u')]

    if args.group_by == 'sections':
        title += [('Status',   '%-10s')]

    result = list()

    if len(relevant):
        title += [('Lines in filter',  '%-15u'),
                  ('Lines percentage', '%-16.2f'),
                  ('Relevant files',   '%-s')]


        for object, counter in relevant.items():
            object_stat = object_stats[object]
            lines_percentage = counter['lines'] / object_stat['lines']

            item = (object if not args.group_by == 'maintainers' 
                                            else pretty_name(object),
                    object_stat['lines'])
            
            if args.bytes:
                item += (object_stat['size'],)

            if args.group_by == 'sections':
                item += (get_status(all_maintainers, object), )

            item += (
                     counter['lines'],
                     lines_percentage,
                     ', '.join({filename for filename in object_files[object] 
                                               if filename in filter_by_files}))


            result.append(item)

        # sort by lines percentage
        result.sort(key=lambda x: x[3])
    else:
        for object, counter in object_stats.items():

            item = (object if not args.group_by == 'maintainers' 
                                            else pretty_name(object),
                    counter['lines'])

            if args.bytes:
                item += (counter['size'],)

            if args.group_by == 'sections':
                item += (get_status(all_maintainers, object), )

            result.append(item)

        # sort by sum lines
        result.sort(key=lambda x: x[1])

    dump_csv(title, result, args.outfile)
