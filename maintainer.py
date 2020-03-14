#!/usr/bin/python

from pypasta.LinuxMaintainers import LinuxMaintainers

from sys import argv

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
argv.pop(0)
print(get_maintainers(argv))
