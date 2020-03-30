"""
This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import sys
import os

from csv import writer
from logging import getLogger
from collections import OrderedDict

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
    try:
        return len(f), f.count('\n')
    # Empty file:
    except:
        return 0 , 0
        
def get_maintainers(config, sub, argv):

    argv.pop(0) # show
    query = argv.pop(0) #entries or maintainers

    # Check to show the detailed view or not
    if '--smallstat' in argv:
        argv.remove('--smallstat')
        optionals = False
    elif '--largestat' in argv:
        # The default option
        argv.remove('--largestat')
        optionals = True
    else:
        optionals = True

    # Decide to output to file or not
    if '--outfile' in argv:
        output_to_file = True
        index = argv.index('--outfile')
        argv.pop(index)
        outfile_name = argv.pop(index)
    else:
        output_to_file = False

    # Is there another MAINTAINERS file given?:
    if '--file' in argv:
        index = argv.index('--file')
        argv.pop(index)
        all_maintainers_text = file_to_string(argv.pop(index))
    else:
        all_maintainers_text = file_to_string('./resources/linux/repo/MAINTAINERS')
    
    if '--filter' in argv:
        index = argv.index('--filter')
        argv.pop(index)
        filenames = file_to_string(argv.pop(index)).splitlines()
        filter_by = True
    else:
        filter_by = False

    total_loc= 0
    all_maintainers = LinuxMaintainers(all_maintainers_text)

    if query == 'entries':
        loc_by_entry = dict()
        byte_by_entry = dict()
        for r, _, f in os.walk('./resources/linux/repo'):
            for item in f:
                filename = os.path.join(r, item)
                # Later needed for the ratio LoC/total LoC
                byte, loc = file_len(str.strip(filename))
                total_loc += loc
                subsystems = all_maintainers.get_subsystems_by_file(filename[23:])
                for subsystem in subsystems:
                    loc_by_entry[subsystem] = loc_by_entry.get(subsystem, 0) + loc
                    byte_by_entry[subsystem] = byte_by_entry.get(subsystem, 0) + byte

        loc_by_entry_filt = dict()
        byte_by_entry_filt = dict()
        if filter_by:
            maintainers = []
            for filename in filenames:
                byte, loc = file_len(str.strip(filename))
                total_loc += loc
                subsystems = all_maintainers.get_subsystems_by_file(filename)
                for subsystem in subsystems:
                    loc_by_entry_filt[subsystem] = loc_by_entry_filt.get(subsystem, 0) + loc
                    byte_by_entry_filt[subsystem] = byte_by_entry.get(subsystem, 0) + byte

            loc_by_entry_filt = OrderedDict(sorted(loc_by_entry_filt.items(), key=lambda x: x[1], reverse=True))
            
        else:
            loc_by_entry_filt = OrderedDict(sorted(loc_by_entry.items(), key=lambda x: x[1], reverse=True))
            byte_by_entry_filt = byte_by_entry

        if optionals:
            if output_to_file:
                with open(outfile_name, 'w+') as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["Entry", "Lines of code","Byte count",  "Lines of code entry/total lines of code"])
                    for entry in loc_by_entry_filt:
                        csv_writer.writerow([entry, loc_by_entry_filt[entry],byte_by_entry_filt[entry], loc_by_entry_filt[entry]/total_loc]) 
            else:
                print("Entry", '\t', "Lines of code", '\t', "Byte count", '\t', "Lines of code entry/total lines of code")
                for entry in loc_by_entry_filt:
                    print(entry, '\t', loc_by_entry_filt[entry], '\t', byte_by_entry_filt[entry] ,'\t', loc_by_entry_filt[entry]/total_loc) 
        else:
            if output_to_file:
                with open(outfile_name, 'w+') as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["Entry", "Byte count", "Lines of code"])
                    for entry in loc_by_entry_filt:
                        csv_writer.writerow([entry, byte_by_entry_filt[entry], loc_by_entry_filt[entry]]) 
            else:
                print("Entry", '\t', "Byte count", '\t', "Lines of code")
                for entry in loc_by_entry_filt:
                    print(entry, '\t',byte_by_entry_filt[entry], '\t', loc_by_entry_filt[entry]) 
        return 0

    elif query == "maintainers":
        loc_by_maintainer = dict()
        byte_by_maintainer = dict()
        for r, _, f in os.walk('./resources/linux/repo'):
            for item in f:
                filename = os.path.join(r, item)

                # Later needed for the ratio LoC/total LoC
                byte, loc = file_len(str.strip(filename))
                total_loc += loc

                # Get all the maintainers for the given repo
                maintainers = []
                subsystems = all_maintainers.get_subsystems_by_file(filename[23:])

                for subsystem in subsystems:
                    maintainers.append(all_maintainers.get_maintainers(subsystem))
                # Map the maintainers to LoC they are tied to
                for maintainer in flatten(flatten(maintainers)):
                    # Strings are mailing lists, maintainers are tuples like ('linus torvalds ', 'torvalds@linux-foundation.org')
                    # 2 tuples are referring to documentation files with name element empty '', eliminate them too
                    if not (type(maintainer) == str or maintainer[0] == '' or maintainer[1] == ''):
                        loc_by_maintainer[maintainer] = loc_by_maintainer.get(maintainer, 0) + loc
                        byte_by_maintainer[maintainer] = byte_by_maintainer.get(maintainer, 0) + byte        
        loc_by_maintainer_filt = dict()
        byte_by_maintainer_filt = dict()
        if filter_by:
            for filename in filenames:
                maintainers = []
                subsystems = all_maintainers.get_subsystems_by_file(filename)
                for subsystem in subsystems:
                    maintainers.append(all_maintainers.get_maintainers(subsystem))
                byte, loc = file_len(str.strip(filename))
                for maintainer in set(flatten(flatten(maintainers))):
                    if not type(maintainer) == str:
                        loc_by_maintainer_filt[maintainer] = loc_by_maintainer_filt.get(maintainer, 0) + loc
                        byte_by_maintainer_filt[maintainer] = byte_by_maintainer_filt.get(maintainer, 0) + byte
                # Order loc_by_maintainer by values:
            loc_by_maintainer_filt = OrderedDict(sorted(loc_by_maintainer_filt.items(), key=lambda x: x[1], reverse=True))
            
        else:
            loc_by_maintainer_filt = OrderedDict(sorted(loc_by_maintainer.items(), key=lambda x: x[1], reverse=True))
            byte_by_maintainer_filt = byte_by_maintainer
            
        if optionals:
            #Detailed view with ratios
            if output_to_file:
                with open(outfile_name, 'w+') as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["Maintainer", "Lines of code in the list", "Total lines of code","Byte count on the list", "Byte count total", "Lines of code in the list/total lines of code in repo"])
                    for maintainer in loc_by_maintainer_filt:
                        csv_writer.writerow([maintainer , loc_by_maintainer_filt[maintainer], loc_by_maintainer[maintainer], byte_by_maintainer_filt[maintainer], byte_by_maintainer[maintainer], loc_by_maintainer_filt[maintainer] /total_loc])
            else:
                print("Maintainer",  '\t',  "Lines of code in the list",  '\t',  "Total lines of code",  '\t', "Byte count on the list", '\t', "Byte count total", '\t', "Lines of code in the list/total lines of code in repo")
                for maintainer in loc_by_maintainer_filt:
                    #<MAINTAINER> \t\t <relevant lines of code for that maintainer based on the filelist> 
                    # (optional: \t <total lines of code for the maintainer> \t <ratio of relevant LoC / total>)
                    print(maintainer , '\t',  loc_by_maintainer_filt[maintainer],  '\t',  loc_by_maintainer[maintainer],  '\t', byte_by_maintainer_filt[maintainer],  '\t',  byte_by_maintainer[maintainer],  '\t', loc_by_maintainer_filt[maintainer] /loc_by_maintainer[maintainer])
        else:
            if output_to_file:
                with open(outfile_name, 'w+') as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["Maintainer", "Lines of code", "Byte count"])
                    for maintainer in loc_by_maintainer_filt:
                        csv_writer.writerow([maintainer , loc_by_maintainer_filt[maintainer], byte_by_maintainer[maintainer]])
            else:
                print("Maintainer",  '\t',  "Lines of code", '\t', "Byte count")
                for maintainer in loc_by_maintainer_filt:
                    #<MAINTAINER> \t\t <relevant lines of code for that maintainer based on the filelist> 
                    print(maintainer,  '\t',  loc_by_maintainer_filt[maintainer], byte_by_maintainer[maintainer])
        return 0
    else:
        print('usage: ./pasta maintainers show entries/maintainers [--filter <filelist text file>] [--file <MAINTAINERS file>] [--outfile <output csv file>] [--smallstat]')
        return -1