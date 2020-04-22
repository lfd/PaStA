"""
PaStA - Patch Stack Analysis
Copyright (c) Bayerische Motoren Werke Aktiengesellschaft (BMW AG), 2020
Copyright (c) OTH Regensburg, 2019-2020
Authors:
  Basak Erdamar <basakerdamar@gmail.com>
This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import os
import pygit2
import sys

from argparse import ArgumentParser
from collections import defaultdict
from csv import writer
from logging import getLogger
from multiprocessing import Pool, cpu_count

sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from pypasta.LinuxMaintainers import load_maintainer
from pypasta.Util import file_to_string

log = getLogger(__name__[-15:])

# We need this global variable, as pygit2 Commit.tree objects are not pickleable
_tmp_tree = None



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


def decreasing_order(dictionary):
    return sorted(dictionary.items(), key=lambda item:item[1].loc, reverse=True)


def get_file_size(filename):
    blob = _tmp_tree[filename]
    lines = blob.data.count(b'\n')
    size = blob.size

    return filename, (lines, size)


def pretty_name(maintainer):
    return maintainer[0]+' <'+maintainer[1]+'>'


def status(all_maintainers, section_name):
    if any(all_maintainers.subsystems[section_name].status):
        return all_maintainers.subsystems[section_name].status[0].value
    else:
        return ''


class Counter:
    def __init__(self, loc=0, byte=0, filter=None):
        self.loc = loc
        self.byte = byte
        self.loc_filt = 0
        self.byte_filt = 0
        if filter:
            self.loc_filt = loc
            self.byte_filt = byte

    def increase(self, loc, byte, filter):
        self.loc += loc
        self.byte += byte
        if filter:
            self.loc_filt += loc
            self.byte_filt += byte

    def display_in_filter(self):
        # whether to show this item in filtered view or not
        if self.byte_filt > 0:
            return True
        return False


def get_counts(all_maintainers, file_sizes, filter_by_files, group_by):
    counts = defaultdict(Counter)
    if  group_by == 'sections':
        filename_excluded = defaultdict(list)
        filenames_filt = defaultdict(list)
    else:
        maintainer_to_section = defaultdict(set)
    for filename, (loc, byte) in file_sizes.items():
        sections = all_maintainers.get_subsystems_by_file(filename)
        sections -= {'THE REST'}
        for section in sections:
            if group_by == 'sections':
                counts[section].increase(loc, byte, filename in filter_by_files)
                if filename in filter_by_files:
                    filenames_filt[section].append(filename)
                else:
                    filename_excluded[section].append(filename)
            else:
                _, maintainers, _ = all_maintainers.get_maintainers(section)
                for maintainer in maintainers:
                    name = pretty_name(maintainer)
                    maintainer_to_section[name].add(section)
                    counts[name].increase(loc, byte, filename in filter_by_files)

    if len(filter_by_files) > 0:
        # If filter is given, only return the relevant lines:
        counts = {name:item for name,item in counts.items()
                    if item.display_in_filter()}
    if group_by == 'sections':
        return decreasing_order(counts), filename_excluded, filenames_filt
    else:
        return decreasing_order(counts), maintainer_to_section


def get_sections_by_files(all_maintainers, filenames):
    results = []
    for filename in filenames:
        sections = all_maintainers.get_subsystems_by_file(filename)
        sections -= {'THE REST'}
        # To get a sense of how large the section is and order by it, look at
        # how many different patterns it includes:
        # all_maintainers.subsystems[section].files
        sections = sorted(sections, 
         key=lambda section: len(all_maintainers.subsystems[section].files))
        results.append([filename, sections])
    return results


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
                        help='files option '
                        'Displays files with corresponding sections\n'
                        'sections option groups files by sections, displays '
                        'sections ordered by lines of code they include\n'
                        'maintainers option groups files by sections, displays '
                        'each maintainer ordered by lines of code they are '
                        'responsible for\n'
                        'Default is sections if no value is specified')
    parser.add_argument('--filesize', action='store_true', 
                                        help='Display file sizes in file mode')
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

    global _tmp_tree
    _tmp_tree = tree
    processes = int(cpu_count())
    p = Pool(processes=processes, maxtasksperchild=1)
    result = p.map(get_file_size, all_filenames)
    p.close()
    p.join()
    _tmp_tree = None

    file_sizes = dict(result)

    if  args.group_by == 'sections':# or not args.group_by:
        title = ['Sections','LoC']
        results, irrelevant_dirs, relevant_dirs = \
         get_counts(all_maintainers, file_sizes, filter_by_files, args.group_by)
    elif args.group_by == 'maintainers':
        title = ['Maintainers', 'LoC']
        results, maintainer_to_section = \
         get_counts(all_maintainers, file_sizes, filter_by_files, args.group_by)
    elif args.group_by == 'files':
        title = ['File name', 'Sections of file']
        victims = filter_by_files if len(filter_by_files) else all_filenames
        results = get_sections_by_files(all_maintainers, victims)
    else:
        parser.print_help()
        sys.exit()

    fields = dict()
    fields['Maintainers'] = fields['Sections'] = fields['File name'] =\
                                                         lambda item : item[0]
    fields['LoC in list'] = lambda item : item[1].loc_filt
    fields['Total LoC'] = fields['LoC'] = lambda item : item[1].loc
    fields['Byte count'] = lambda item : item[1].byte
    fields['In list(%)']=lambda item:round((item[1].loc_filt/item[1].loc)*100,2)
    fields['Status'] = lambda item : status(all_maintainers, item[0])
    fields['Sections of maintainer'] = \
                         lambda item:', '.join(maintainer_to_section[item[0]])
    fields['Irrelevant files'] = lambda item: ','.join(irrelevant_dirs[item[0]])
    fields['Relevant files'] = lambda item: ','.join(relevant_dirs[item[0]])
    fields['Sections of file'] = lambda item : ','.join(item[1])
    fields['LoC of file'] = lambda item : file_sizes[item[0]][0]

    if args.bytes:
        title += ['Byte count']
    if not args.smallstat:
        if args.filter and not args.group_by == 'files':
            title += ['LoC in list', 'In list(%)']
            if  args.group_by == 'sections':
                title += ['Relevant files', 'Irrelevant files']
        if  args.group_by == 'sections':
            title.insert(1, 'Status')
        elif args.group_by =='maintainers':
            title += ['Sections of maintainer']
        elif  args.group_by == 'files' and args.filesize:
            title.insert(1, 'LoC of file')


    results = [[fields[field](item) for field in title] for item in results]
    results.insert(0, title)
    if args.outfile:
        with open(args.outfile, 'w+') as csv_file:
            csv_writer = writer(csv_file)
            csv_writer.writerows(results)
    else:
        width = len(max(list(zip(*results))[0], key = len))
        _, columns = os.popen('stty size', 'r').read().split()
        columns = int(columns)
        for line in results:
            line_s = str(line[0]).ljust(width+4)
            for item in line[1:]:
                line_s += str(item).ljust(15)
            if len(line_s) > columns:
                print(line_s[0:columns-3]+"...")
            else:
                print(line_s)

    return 0
