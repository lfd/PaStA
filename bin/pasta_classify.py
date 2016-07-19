#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2018

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import os
import random
import sys

from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *

from pypasta.PatchClassification import *

_clf = None
_repo = None


def _prediction_helper(hash):
    return predict_patch_classes(_clf, _repo, hash)


def classify(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='Interactive Rating: Rate evaluation results')

    parser.add_argument('-ts', dest='training_set', metavar='filename',
                        help='training set filename (default: %(default)s)', default='./trainset')
    parser.add_argument('-hs', dest='hash_set', metavar='filename',
                        help='hash set filename. Either used for training or prediction. '
                             'If not provided, a random sample set is chosen')
    parser.add_argument('-pf', dest='prediction_file', metavar='filename',
                        help='prediction_file', default='./prediction')
    parser.add_argument('-ss', dest='sample_size', type=int, metavar='size',
                        help='sample size, 0 means all samples (default: %(default)s)', default=0)
    parser.add_argument('-r', dest='randomise', action='store_true', help='randomise sample set')
    parser.add_argument('-v', dest='verbose', action='store_true', help='verbose output')
    parser.add_argument('mode', choices=['train', 'predict'],
                        help='Mode: train or predict')

    args = parser.parse_args(argv)
    repo = config.repo

    if args.hash_set:
        hash_set = get_commits_from_file(args.hash_set, ordered=True, must_exist=True)
    else:
        hash_set = list(config.psd.upstream_hashes)

    if args.sample_size == 0:
        args.sample_size = len(hash_set)

    if args.randomise:
        if args.verbose:
            print('Choosing a random sample set from hash set of size %d' % args.sample_size)
        sample_set = random.sample(hash_set, args.sample_size)
    else:
        sample_set = hash_set[0:args.sample_size]

    # load commit cache
    repo.load_ccache(config.f_ccache_classify, must_exist=False)

    # load trainset
    if args.verbose:
        print('Loading training set...')
    training_set = TrainingSet.from_file(args.training_set, must_exist=False)
    repo.cache_commits(training_set.keys())

    clf = get_classifier(repo, training_set)
    if args.verbose:
        print('Training set consists of %d classified commits' % len(training_set))
        print('Feature importances:')
        print(clf.feature_importances_)
        print('Press any key')
        getch()

    if args.mode == 'train':
        for hash in sample_set:
            prediction = None
            if clf:
                _, prediction = predict_patch_classes(clf, repo, hash)
            classification = train_commit(repo, hash, prediction)
            # Check if classification is aborted or skipped
            if classification is None:
                break
            elif len(classification) == 0:
                continue
            # Add classification to training set
            training_set[hash] = classification

        training_set.to_file(args.training_set, args.verbose)
        repo.export_ccache(config.f_ccache_classify)
    elif args.mode == 'predict':
        if clf is None:
            raise RuntimeError('Prediction without training set not possible.')

        repo.cache_commits(sample_set)
        if args.verbose:
            print('Predicting %d commits...' % len(sample_set))

        global _clf
        global _repo
        _clf = clf
        _repo = repo

        p = Pool(cpu_count())
        prediction = p.map(_prediction_helper, sample_set)
        p.close()
        p.join()

        _repo = None
        _clf = None

        prediction = TrainingSet(prediction)
        prediction.to_file(args.prediction_file, args.verbose)
    else:
        raise ValueError('Unknown mode: %s' % args.mode)


if __name__ == '__main__':
    config = Config(sys.argv[1])
    classify(config, sys.argv[0], sys.argv[2:])
