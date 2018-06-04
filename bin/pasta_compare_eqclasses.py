#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2018

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import os
import sys

from logging import getLogger
from sklearn import metrics
from itertools import combinations

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *

log = getLogger(__name__[-15:])


def prec_rec(ground_truth, prediction):
    ground_truth_keys = ground_truth.get_keys()
    prediction_keys = prediction.get_keys()

    combs = list(combinations(ground_truth_keys | prediction_keys, 2))
    false_positives = 0
    true_positives = 0
    false_negatives = 0
    true_negatives = 0

    for source, dest in combs:
        truth = ground_truth.is_related(source, dest)
        pred = prediction.is_related(source, dest)

        if (truth, pred) == (True, True):
            true_positives += 1
        elif (truth, pred) == (False, False):
            true_negatives += 1
        elif (truth, pred) == (False, True):
            false_positives += 1
        elif (truth, pred) == (True, False):
            false_negatives += 1

    log.info('')
    log.info('Comparisons: %d' % len(combs))
    log.info('True Positives: %d' % true_positives)
    log.info('True Negatives: %d' % true_negatives)
    log.info('False Positives: %d' % false_positives)
    log.info('False Negatives: %d' % false_negatives)

    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)
    fmeasure = 2 * precision * recall / (precision + recall)

    log.info('  Precision: %f' % precision)
    log.info('  Recall: %f' % recall)
    log.info('  F-Measure: %f' % fmeasure)


def compare_eqclasses(prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Compare Equivalence Classes')
    parser.add_argument('classes', metavar='eqclass', type=str, nargs=2,
                        help='Ground Truth / Prediction')
    parser.add_argument('-ar', action='store_true', default=False,
                        help='Adjusted rand score')
    parser.add_argument('-mi', action='store_true', default=False,
                        help='Mutual info score')
    parser.add_argument('-ami', action='store_true', default=False,
                        help='Adjusted mutual info score')
    parser.add_argument('-nmi', action='store_true', default=False,
                        help='Normalised mutual info score')
    parser.add_argument('-pur', action='store_true', default=False,
                        help='Purity')
    parser.add_argument('-pr', action='store_true', default=False,
                        help='Classic Precision/Recall')
    parser.add_argument('-fm', action='store_true', default=False,
                        help='Fowlkes-Mallow score')
    parser.add_argument('-remove-identical', action='store_true', default=False,
                        help='Remove identical clusters before comparing')
    parser.add_argument('-f', type=str, help='Write results to filename')
    parser.add_argument('-test', action='store_true', default=False,
                        help='run tests')

    args = parser.parse_args(argv)

    # These are the converted example from:
    # https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-clustering-1.html

    if args.test:
        ground_truth = Cluster()
        prediction = Cluster()

        prediction.insert(0,1,2,3,4,5)
        prediction.insert(6,7,8,9,10,11)
        prediction.insert(12, 13, 14, 15, 16)

        ground_truth.insert(0,2,3,4,5,6,12,14)
        ground_truth.insert(1, 7, 8, 9, 11)
        ground_truth.insert(10,13,15,16)
    else:
        ground_truth = Cluster.from_file(args.classes[0], must_exist=True)
        prediction = Cluster.from_file(args.classes[1], must_exist=True)

    # remove identical clusters, if desired
    if args.remove_identical:
        identical = list()
        for cluster in ground_truth:
            cand = prediction.get_cluster(list(cluster)[0])
            if not cand:
                continue
            elif cand == cluster:
                identical.append(cand)
        log.info('Removing %d identical clusters (%d elements)...' %
                 (len(identical), sum([len(x) for x in identical])))
        for cluster in identical:
            for element in cluster:
                ground_truth.remove_key(element)
                prediction.remove_key(element)
        ground_truth.optimize()
        prediction.optimize()

    if (args.pr):
        prec_rec(ground_truth, prediction)

    # intermix all keys
    ground_truth_keys = ground_truth.get_keys()
    prediction_keys = prediction.get_keys()

    missing = ground_truth_keys - prediction_keys
    log.info('%d keys missing in prediction' % len(missing))
    for key in missing:
        prediction.insert_single(key)

    missing = prediction_keys - ground_truth_keys
    log.info('%d keys missing in ground truth' % len(missing))
    for key in missing:
        ground_truth.insert_single(key)

    gt = list(sorted(ground_truth.lookup.items()))
    t = list(sorted(prediction.lookup.items()))

    gt = [x[1] for x in gt]
    t = [x[1] for x in t]

    log.info('Number of equiv classes: %d' % len(ground_truth))

    homo, comp, vm = metrics.homogeneity_completeness_v_measure(gt, t)
    log.info("Homogeneity: %0.3f" % homo)
    log.info("Completeness: %0.3f" % comp)
    log.info("V-measure: %0.3f" % vm)

    if args.ar:
        ar = metrics.adjusted_rand_score(gt, t)
        log.info("Adjusted rand score: %0.3f" % ar)
    if args.mi:
        mi = metrics.mutual_info_score(gt, t)
        log.info("Mutual info score: %0.3f" % mi)
    if args.ami:
        ami = metrics.adjusted_mutual_info_score(gt, t)
        log.info("Adjusted mutual info score: %0.3f" % ami)
    if args.nmi:
        nmi = metrics.normalized_mutual_info_score(gt, t)
        log.info("Normalised mutual info score: %0.3f" % nmi)
    if args.pur:
        elements = len(gt)
        hits = 0
        for w in ground_truth:
            this = 0
            for element in w:
                tmp = prediction[element]
                foo = len(w & tmp)
                if foo > this:
                    this = foo
            hits += this
        purity = hits / elements
        log.info('Purity: %0.3f' % purity)
    if args.fm:
        fm = metrics.fowlkes_mallows_score(gt, t)
        log.info("Fowlkes-Mallows score: %0.3f" % fm)

    if args.f:
        with open(args.f, 'w') as f:
            f.write("homo: %0.3f\n" % homo)
            f.write("comp: %0.3f\n" % comp)
            f.write("vm: %0.3f\n" % vm)
            if args.ar:
                f.write("ar: %0.3f\n" % ar)
            if args.mi:
                f.write("mi: %0.3f\n" % mi)
            if args.nmi:
                f.write("nmi: %0.3f\n" % nmi)
            if args.ami:
                f.write("ami: %0.3f\n" % ami)
            if args.pur:
                f.write("pur: %0.3f\n" % purity)
            if args.fm:
                f.write("fm: %0.3f\n" % fm)

    return 0


if __name__ == '__main__':
    ret = compare_eqclasses(sys.argv[0], sys.argv[1:])
    sys.exit(ret)
