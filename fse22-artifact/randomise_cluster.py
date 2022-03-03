#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis
A tool for tracking the evolution of patch stacks

Copyright (c) OTH Regensburg, 2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import glob
import os
import random
import re
import sys

def sanitise(s):
	s = re.sub('\\\\', '', s)
	s = re.sub(r'([_^$%&#{}])', r'\\\1', s)
	s = re.sub(r'\~', r'\\~{}', s)
	return s

vertex_names = sys.argv[1]
d_cluster = sys.argv[2]
f_clusters = glob.glob(os.path.join(d_cluster, 'cluster_*_standalone.tex'))

with open(vertex_names, 'r') as f:
    vertex_names = list(filter(None, f.read().split('\n')))
random.shuffle(vertex_names)

for f_cluster_tex in f_clusters:
    print('Replacing %s...' % f_cluster_tex)
    with open(f_cluster_tex, 'r') as f:
        tex = f.read().split('\n')

    with open(os.path.join(os.path.dirname(f_cluster_tex), 'random_%s' % os.path.basename(f_cluster_tex)), 'w') as f:
        for line in tex:
            if line.startswith('\\node'):
                line = re.sub('{.*}', '{%s}' % sanitise(vertex_names.pop()), line)
            f.write('%s\n' % line)
