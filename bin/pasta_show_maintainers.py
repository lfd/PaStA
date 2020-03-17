"""
This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

# ./pasta maintainers drivers/acpi/acpica/accommon.h sound/atmel/ac97c.c
# ./pasta maintainers --file ./resources/linux/repo/MAINTAINERS  drivers/acpi/acpica/accommon.h sound/atmel/ac97c.c

import sys
import os

from logging import getLogger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pypasta.LinuxMaintainers import LinuxMaintainers

log = getLogger(__name__[-15:])

def get_maintainers(config, sub, argv):

    if argv[0] == '--file':
        argv.pop(0)
        all_maintainers = open(argv.pop(0), 'r').read()
    else:
        all_maintainers = open('./resources/linux/repo/MAINTAINERS', 'r').read()

    all_maintainers = LinuxMaintainers(all_maintainers)
    
    results = dict()
    for filename in argv:
        subsystem = all_maintainers.get_subsystems_by_file(filename)
        maintainer = all_maintainers.get_maintainers(subsystem.pop())
        results[filename] = maintainer
    
    return results
