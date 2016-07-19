"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2018

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import numpy
import os
import re

from enum import Enum
from termcolor import colored

from sklearn import tree

from .PatchClassificationFeatures import get_features
from .Util import *

CLASSIFICATION_ENTRY = re.compile(r'([0-9a-f]{40})\s+(.*)', re.IGNORECASE)
PREDICT_THRESHOLD = 0.75


class PatchClass(Enum):
    Fix = 0
    Feat = 1
    FeatPrep = 2
    FeatEnable = 3
    FeatureRem = 4
    Prev = 5
    Perf = 6
    Refactor = 7
    ApiChange = 8
    Efficiency = 9
    MergeCommit = 10
    Comment = 11
    Documentation = 12
    Licensing = 13

    @staticmethod
    def from_string(string):
        string = string.lower()
        for patchClass in PatchClass:
            if patchClass.name.lower() == string:
                return patchClass
        raise ValueError('Unknown patch class: %s' % string)


class TrainingSet(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def to_file(self, filename, verbose=False):
        if verbose:
            print('Saving %d classified commits' % len(self))
        with open(filename, 'w') as f:
            items = sorted(self.items(), key=lambda x: x[0])
            for hash, classification in items:
                classes = sorted([x.name for x in classification])
                classes = ', '.join(classes)
                f.write('%s %s\n' % (hash, classes))

    @staticmethod
    def from_file(filename, must_exist=True):
        trainset = TrainingSet()
        if os.path.isfile(filename):
            with open(filename, 'r') as f:
                entries = f.read().splitlines()
            for entry in entries:
                match = CLASSIFICATION_ENTRY.match(entry)
                hash = match.group(1)
                classes = match.group(2).split(',')
                classes = {PatchClass.from_string(x.strip()) for x in classes}
                trainset[hash] = classes
        elif must_exist:
            raise FileNotFoundError('Could not find trainset %s' % filename)
        return trainset


def train_commit(repo, hash, prediction=None):
    """
    Train a specific commit hash
    :param repo: Repository
    :param hash: Hash to train
    :param prediction: Predicted classification set. Can be an empty set or None.
    :return: None on abort, set() on skip and set of PatchClasses on success
    """
    if not prediction:
        prediction = set()

    def print_labels():
        sys.stdout.write('\r')
        for c in PatchClass:
            color = 'green' if c in prediction else 'red'
            text = '%s(%x)  ' % (c.name, c.value)
            sys.stdout.write(colored(text, color))
        sys.stdout.flush()

    show_commit(repo, hash)
    print('-------------------------------')
    print(colored('Accept (Enter), Stop (Escape), Skip (s)', 'blue'))
    while True:
        print_labels()
        try:
            input = getch()
            if input == '\r':
                return prediction
            elif input == '\x1b':
                print()
                return None
            elif input == 's':
                return set()
            else:
                c = PatchClass(int(input, 16))
                if c in prediction:
                    prediction.remove(c)
                else:
                    prediction.add(c)
        except ValueError:
            pass


def get_classifier(repo, training_set):
    """
    Returns a sklearn classifier
    Can return None if training set is empty
    :param training_set: Training set
    :return: Classifier or None
    """
    if len(training_set) == 0:
        return None

    X = []
    Y = []
    for hash, classification in sorted(training_set.items(), key=lambda x: x[0]):
        features = get_features(repo, hash)
        X.append(features)
        y = [(x in classification) for x in PatchClass]
        Y.append(y)

    clf = tree.DecisionTreeClassifier(criterion='entropy', presort=True)
    clf = clf.fit(X, Y)

    return clf


def predict_patch_classes(clf, repo, hash, threshold=PREDICT_THRESHOLD):
    predict = clf.predict([get_features(repo, hash)])[0]
    predict = numpy.where(predict >= threshold)[0]
    predict = {PatchClass(x) for x in predict}
    return hash, predict
