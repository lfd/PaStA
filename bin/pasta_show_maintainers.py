"""

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pypasta.LinuxMaintainers import LinuxMaintainers


def get_maintainers(filenames):
    results = list()
    maintainers = open('./resources/linux/repo/MAINTAINERS', 'r').read()
    maintain = LinuxMaintainers(maintainers)

    for filename in filenames:
        subsystem = maintain.get_subsystems_by_file(filename)
        maintainer = maintain.get_maintainers(subsystem.pop())
        results.append((filename, subsystem, maintainer))
    return results
#(PaStA) basak@pop-os:~/Documents/PaStA$ python ./maintainer.py repo/drivers/acpi/acpica/accommon.
sys.argv.pop(0)
print(get_maintainers(sys.argv))
