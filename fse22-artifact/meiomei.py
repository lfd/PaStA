#!/usr/bin/env python3

import csv
import sys
from collections import defaultdict

filename = sys.argv[1]

clusters=defaultdict(set)

with open(filename, 'r') as f:
    c = csv.DictReader(f)
    for row in c:
        clusters[row['c_representative']].add(row['c_section'])

out = str()
for vals in clusters.values():
    vals = [v.replace(' ', '') for v in vals]
    out += ' '.join(vals) + '\n'

out = out.strip()
print(out)
