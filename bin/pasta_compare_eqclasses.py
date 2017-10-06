#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *


def compare_eqclasses(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='Compare Equivalence Classes')
    parser.add_argument('classes', metavar='eqclass', type=str, nargs=2,
                        help='Prediction / Ground Truth')

    args = parser.parse_args(argv)

    prediction = EquivalenceClass.from_file(args.classes[0], must_exist=True)
    ground_truth = EquivalenceClass.from_file(args.classes[1], must_exist=True)

    relevant = set()

    false_positives = 0
    true_positives = 0

    false_negatives = 0

    for prop_entry in ground_truth.transitive_list:
        property = prop_entry.property
        if prop_entry.property is None:
            print('handle this case')
            quit()

        for list_entry in prop_entry:
            relevant |= {list_entry}
            if list_entry in prediction:
                pred_prop = prediction.get_property(list_entry)
                if pred_prop is None:
                    print('handle this case..')
                    quit()
                elif pred_prop == property:
                    true_positives += 1
                else:
                    false_positives += 1
            else:
                false_negatives += 1

    for prop_entry in prediction:
        for list_entry in prop_entry:
            relevant |= {list_entry}
            if list_entry not in ground_truth:
                false_positives += 1


    print()
    print('Relevant Elements: %d' % len(relevant))
    print('False Positives: %d' % false_positives)
    print('False Negatives: %d' % false_negatives)
    print('True Positives: %d' % true_positives)

    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)

    print('  Precision: %f' % precision)
    print('  Recall: %f' % recall)

if __name__ == '__main__':
    config = Config(sys.argv[1])
    compare_eqclasses(config, sys.argv[0], sys.argv[2:])
