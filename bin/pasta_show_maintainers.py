"""
This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import sys
import os

from logging import getLogger

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pypasta.LinuxMaintainers import LinuxMaintainers
from pypasta.Util import file_to_string

log = getLogger(__name__[-15:])

def flatten(nested):
    flat_list = []
    for sublist in nested:
        for item in sublist:
            flat_list.append(item)
    return flat_list

def file_len(filename):
    f = file_to_string(filename)
    for i, l in enumerate(f):
        pass
    return i + 1

def get_maintainers(config, sub, argv):

    if '--smallstat' in argv:
        index = argv.index('--smallstat')
        argv.pop(index)
        optionals = False
    elif '--largestat' in argv:#the default option
        index = argv.index('--largestat')
        argv.pop(index)
        optionals = True
    else:
        optionals = True

    if '--file' in argv:
        index = argv.index('--file')
        argv.pop(index)
        all_maintainers_text = file_to_string(argv.pop(index))
    else:
        all_maintainers_text = file_to_string('./resources/linux/repo/MAINTAINERS')
    
    all_kernel_files = []
    filenames = []
    total_loc= 0
    loc_by_subsystem = dict()
    all_maintainers = LinuxMaintainers(all_maintainers_text)

    for r, d, f in os.walk('./resources/linux/repo/kernel/'):
        for item in f:
            filename = os.path.join(r, item)
            # Maybe keep all lenghts per file as a dict as well&use later instead of re-calculating? Is is worth the memory?
            loc = file_len(filename)
            for subsystem in all_maintainers.get_subsystems_by_file(filename):
                loc_by_subsystem[subsystem] = loc_by_subsystem.get(subsystem, 0) + loc
            total_loc += loc
            all_kernel_files.append(filename)

    if '--filter' in argv:
        index = argv.index('--filter')
        argv.pop(index)
        filenames = file_to_string(argv.pop(index)).splitlines()
    else:
        filenames = all_kernel_files

    argv.pop(0) #show
    query = argv.pop(0) #entries or maintainers

    if query == 'entries':

        #print('File name\tLines of code\tLines of code / Total lines of code')
        for filename in filenames:
            loc = file_len(str.strip(filename))
            if optionals:
                print(filename + '\t' + str(loc) + '\t' + str(loc/total_loc))
            else:
                print(filename + '\t' + str(loc))
    elif query == "maintainers":

        maintainers = []
        print('Maintainers of:')
        for filename in filenames:
            subsystems = all_maintainers.get_subsystems_by_file(filename)
            for subsystem in subsystems:
                maintainers.append(all_maintainers.get_maintainers(subsystem))

            print('\n' + filename + ':')
            for entry in set(flatten(flatten(maintainers))):
                if type(entry) is str:
                    print('\t', entry)
                else:
                    print('\t', entry[0], entry[1])
        return 0
    else:
        print('usage: ./pasta maintainers show entries/maintainers [--filter <filelist text file>] [--file <MAINTAINERS file>]')
        return -1
