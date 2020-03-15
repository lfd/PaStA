"""

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

# python  ./bin/pasta_show_maintainers.py drivers/acpi/acpica/accommon.h sound/atmel/ac97c.c

import sys
import os

from logging import getLogger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pypasta.LinuxMaintainers import LinuxMaintainers

log = getLogger(__name__[-15:])

def get_maintainers(config, sub, argv):
    results = list()
    maintainers = open('./resources/linux/repo/MAINTAINERS', 'r').read()
    maintain = LinuxMaintainers(maintainers)

    for filename in argv:
        subsystem = maintain.get_subsystems_by_file(filename)
        maintainer = maintain.get_maintainers(subsystem.pop())
        results.append((filename, subsystem, maintainer))
    return results

#sys.argv.pop(0)
#print(*get_maintainers(sys.argv), sep='\n')
