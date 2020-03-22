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
    try:
        return i + 1
    except:
        return 0
        
    

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
    loc_by_maintainer = dict()
    all_maintainers = LinuxMaintainers(all_maintainers_text)

    for r, d, f in os.walk('./resources/linux/repo/kernel/'):
        for item in f:
            filename = os.path.join(r, item)
            all_kernel_files.append(filename)
            # Maybe keep all lenghts per file as a dict as well&use later instead of re-calculating? Is is worth the memory?
            loc = file_len(filename)
            total_loc += loc
            subsystems = all_maintainers.get_subsystems_by_file(filename)
            maintainers = []
            for subsystem in subsystems:
                maintainers.append(all_maintainers.get_maintainers(subsystem))

            for entry in set(flatten(flatten(maintainers))):
                loc_by_maintainer[entry] = loc_by_maintainer.get(entry, 0) + loc
    
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
        return 0

    elif query == "maintainers":

        maintainers = []
        loc_by_maintainer_filt = dict()
        print('Lines of code for maintainers:')
        for filename in filenames:
            subsystems = all_maintainers.get_subsystems_by_file(filename)
            for subsystem in subsystems:
                maintainers.append(all_maintainers.get_maintainers(subsystem))
            
            loc = file_len(str.strip(filename))
            for entry in set(flatten(flatten(maintainers))):
                loc_by_maintainer_filt[entry] = loc_by_maintainer_filt.get(entry, 0) + loc
            
        if optionals:
            print("Maintainer",  '\t',  "Lines of code in the list",  '\t',  "Total lines of code",  '\t',  "Lines of code in the list/total lines of code")
            for maintainer in loc_by_maintainer_filt:
                #<MAINTAINER> \t\t <relevant lines of code for that maintainer based on the filelist> 
                # (optional: \t <total lines of code for the maintainer> \t <ratio of relevant LoC / total>)
                print(maintainer , '\t',  loc_by_maintainer_filt[maintainer],  '\t',  loc_by_maintainer[maintainer],  '\t',  loc_by_maintainer_filt[maintainer] /loc_by_maintainer[maintainer])
        else:
            print("Maintainer",  '\t',  "Lines of code")
            for maintainer in loc_by_maintainer_filt:
                #<MAINTAINER> \t\t <relevant lines of code for that maintainer based on the filelist> 
                print(maintainer,  '\t',  loc_by_maintainer_filt[maintainer])
        return 0
    else:
        print('usage: ./pasta maintainers show entries/maintainers [--filter <filelist text file>] [--file <MAINTAINERS file>]')
        return -1
