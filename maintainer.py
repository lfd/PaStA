#!/usr/bin/python

from pypasta.LinuxMaintainers import LinuxMaintainers

from sys import argv

def get_maintainers(filenames):
    print(filenames)
    maintainers = open('./resources/linux/repo/MAINTAINERS', 'r').read()
    maintain = LinuxMaintainers(maintainers)
    for filename in filenames:
        subsystem = maintain.get_subsystems_by_file(filename)
        maintainer = maintain.get_maintainers(subsystem)
        return(filename, subsystem, maintainer)

print('Number of arguments:', len(argv), 'arguments.')
print( 'Argument List:', str(argv))
argv.pop(0)
print(type(argv))
filenames = list(argv)
print(type(filenames))
print(get_maintainers(filenames))



