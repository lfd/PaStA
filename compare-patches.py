#!/usr/bin/env python3

import sys

from PatchEvaluation import evaluate_single_patch

commit_a = sys.argv[1]
commit_b = sys.argv[2]

retval = evaluate_single_patch(commit_a, commit_b)
if retval is None:
    print('None')
else:
    hash, rating, message = retval
    print('Rating: ' + str(rating) + ' ' + message)
