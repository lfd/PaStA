"""
This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

# ./pasta maintainers --filter /home/q503670/file_list --file ./resources/linux/repo/MAINTAINERS

import sys
import os

from logging import getLogger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pypasta.LinuxMaintainers import LinuxMaintainers
from pypasta.Util import file_to_string

log = getLogger(__name__[-15:])

def flatten(nested):
    flat_list = []
    for sublist in nested:
        for item in sublist:
            flat_list.append(item)
    return flat_list

def get_maintainers(config, sub, argv):
        
    if argv.pop(0) == '--filter':
        filenames = file_to_string(argv.pop(0)).splitlines()
    else:
        print('usage: ./pasta maintainers --filter <filelist text file> [--file <MAINTAINERS file>]')
        exit()
        
    if argv[0] == '--file':
        argv.pop(0)
        all_maintainers_text = file_to_string(argv.pop(0))
    else:
        all_maintainers_text = file_to_string('./resources/linux/repo/MAINTAINERS')

    all_maintainers = LinuxMaintainers(all_maintainers_text)

    subsystems = all_maintainers.get_subsystems_by_files(filenames)

    results = list()
    for subsystem in subsystems:
        maintainer = all_maintainers.get_maintainers(subsystem)
        results.append(maintainer[1])
    