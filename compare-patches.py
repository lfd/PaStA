#!/usr/bin/env python3

import sys

from PatchEvaluation import preevaluate_single_patch, evaluate_single_patch

commit_a = sys.argv[1]
commit_b = sys.argv[2]

retval = preevaluate_single_patch(commit_a, commit_b)
#retval = True
if retval:
    print('Preevaluation: Possible candidates')
    retval = evaluate_single_patch(commit_a, commit_b)
    if retval is None:
        print('Rating: 0')
    else:
        hash, rating, message = retval
        print('Rating: ' + str(rating) + ' ' + message)
else:
    print('Preevaluation: Not related')