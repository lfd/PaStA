"""
This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import sys
import os

from csv import writer
from multiprocessing import cpu_count, Pool
from itertools import chain
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

all_maintainers = LinuxMaintainers.__class__

def worker(filename):
            
    # Later needed for the ratio LoC/total LoC
    loc = file_len(filename)

    # Get all the maintainers for the given file
    maintainers = []
    subsystems = all_maintainers.get_subsystems_by_file(filename)

    for subsystem in subsystems:
        maintainers.append(all_maintainers.get_maintainers(subsystem))

    return filename, loc, set(flatten(flatten(maintainers)))

def get_maintainers(config, sub, argv):

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
    
    global all_maintainers
    all_maintainers = LinuxMaintainers(all_maintainers_text)


    
    num_cpus = int(cpu_count() * 0.75)
    
    with Pool(num_cpus) as  pool:
        # TODO: Check to see if this is the right path to walk!
        walk = os.walk('./resources/linux/repo/')
        iterator = chain.from_iterable((os.path.join(root, file)
                                                for file in files)
                                               for root, dirs, files in walk)
        results = pool.map(worker, iterator)

    total_loc= 0
    loc_by_maintainer = dict()
    all_kernel_files = []
    for filename, loc, maintainers in results:
        all_kernel_files.append(filename)
        total_loc += loc
        for maintainer in maintainers:
            print(maintainer, filename)
            loc_by_maintainer[maintainer] = loc_by_maintainer.get(maintainer, 0) + loc

    if '--filter' in argv:
        index = argv.index('--filter')
        argv.pop(index)
        filenames = file_to_string(argv.pop(index)).splitlines()
    else:
        filenames = all_kernel_files

    argv.pop(0) # show
    query = argv.pop(0) #entries or maintainers

    if query == 'entries':
        if optionals:
            if output_to_file:
                with open(outfile_name, 'w+') as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["File", "Lines of code", "Lines of code file/total lines of code"])
                    for filename in filenames:
                        csv_writer.writerow([filename, str(loc), str(loc/total_loc)]) 
            else:
                for filename in filenames:
                    loc = file_len(str.strip(filename))
                    print(filename + '\t\t' + str(loc) + '\t\t' + str(loc/total_loc)) 
        else:
            if output_to_file:
                with open(outfile_name, 'w+') as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["File", "Lines of code"])
                    for filename in filenames:
                        loc = file_len(str.strip(filename))
                        csv_writer.writerow([filename, str(loc)]) 
            else:
                for filename in filenames:
                    loc = file_len(str.strip(filename))
                    print(filename + '\t\t' + str(loc))
        return 0

    elif query == "maintainers":

        maintainers = []
        loc_by_maintainer_filt = dict()
        for filename in filenames:
            subsystems = all_maintainers.get_subsystems_by_file(filename)
            for subsystem in subsystems:
                maintainers.append(all_maintainers.get_maintainers(subsystem))
            
            loc = file_len(str.strip(filename))
            for entry in set(flatten(flatten(maintainers))):
                loc_by_maintainer_filt[entry] = loc_by_maintainer_filt.get(entry, 0) + loc
            
        if optionals:
            #Detailed view with ratios
            if output_to_file:
                with open(outfile_name, 'w+') as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["Maintainer", "Lines of code in the list", "Total lines of code", "Lines of code in the list/total lines of code"])
                    for maintainer in loc_by_maintainer_filt:
                        csv_writer.writerow([maintainer , loc_by_maintainer_filt[maintainer], loc_by_maintainer[maintainer], loc_by_maintainer_filt[maintainer] /loc_by_maintainer[maintainer]])
            else:
                print("Maintainer",  '\t\t',  "Lines of code in the list",  '\t\t',  "Total lines of code",  '\t\t',  "Lines of code in the list/total lines of code")
                for maintainer in loc_by_maintainer_filt:
                    #<MAINTAINER> \t\t <relevant lines of code for that maintainer based on the filelist> 
                    # (optional: \t <total lines of code for the maintainer> \t <ratio of relevant LoC / total>)
                    print(maintainer , '\t\t',  loc_by_maintainer_filt[maintainer],  '\t\t',  loc_by_maintainer[maintainer],  '\t\t',  loc_by_maintainer_filt[maintainer] /loc_by_maintainer[maintainer])
        else:
            if output_to_file:
                with open(outfile_name, 'w+') as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["Maintainer", "Lines of code"])
                    for maintainer in loc_by_maintainer_filt:
                         csv_writer.writerow([maintainer, loc_by_maintainer_filt[maintainer]])
            else:
                print("Maintainer",  '\t',  "Lines of code")
                for maintainer in loc_by_maintainer_filt:
                    #<MAINTAINER> \t\t <relevant lines of code for that maintainer based on the filelist> 
                    print(maintainer,  '\t',  loc_by_maintainer_filt[maintainer])
        return 0
    else:
        print('usage: ./pasta maintainers show entries/maintainers [--filter <filelist text file>] [--file <MAINTAINERS file>] [--outfile <output csv file>] [--smallstat]')
        return -1
