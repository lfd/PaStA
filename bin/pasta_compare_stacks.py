#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import os
import sys

from functools import partial

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *


# copied from: http://stackoverflow.com/questions/6076690/verbose-level-with-argparse-and-multiple-v-options
class VAction(argparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        # print 'values: {v!r}'.format(v=values)
        if values==None:
            values='1'
        try:
            values=int(values)
        except ValueError:
            values=values.count('v')+1
        setattr(args, self.dest, values)


def print_flow(repo, commits, destinations=None, verbosity=0, indent=4):
    if verbosity < 1:
        return
    if destinations:
        destinations = dict(destinations)
    for commit in commits:
        commit = repo[commit]

        sys.stdout.write(' ' * indent)
        sys.stdout.write(commit.commit_hash)
        if verbosity > 1:
            sys.stdout.write(' : %s (%s)' % (commit.subject, commit.author))
        sys.stdout.write('\n')
        if verbosity > 2 and destinations:
            dsts = [repo[x] for x in destinations[commit.commit_hash]]
            for dst in dsts:
                sys.stdout.write(' ' * (indent+2))
                sys.stdout.write('|-> %s ' % dst.commit_hash)
                if verbosity > 3:
                    sys.stdout.write('%s (%s)' % (dst.subject, dst.author))
                sys.stdout.write('\n')


def print_upstream(repo, patch_groups, x, verbosity, indent=4):
    print_flow(repo, x, [(x, [patch_groups.get_property(x)]) for x in x], verbosity=verbosity, indent=indent)


def compare_stack_against_stack(repo, patch_groups, date_selector, stack_from, stack_to, verbosity=0):
    my_print_upstream = partial(print_upstream, repo, patch_groups, verbosity=verbosity)

    flow = PatchFlow.compare_stack_releases(patch_groups, stack_from, stack_to)
    print('Invariant: %d' % len(flow.invariant))
    composition = PatchComposition.from_commits(repo, patch_groups, date_selector, [x[0] for x in flow.invariant])
    print('  just invariant: %d' % len(composition.none))
    print_flow(repo, composition.none, flow.invariant, verbosity)
    print('  still backports: %d' % len(composition.backports))
    print_flow(repo, composition.backports, flow.invariant, verbosity)
    print('  will go upstream in future: %d' % len(composition.forwardports))
    print_flow(repo, composition.forwardports, flow.invariant, verbosity)

    print('Dropped: %d' % len(flow.dropped))
    composition = PatchComposition.from_commits(repo, patch_groups, date_selector, flow.dropped)
    print('  just dropped: %d' % len(composition.none))
    print_flow(repo, composition.none, verbosity=verbosity)
    print('  no longer needed, as patches were backports: %d' % len(composition.backports))
    my_print_upstream(composition.backports)
    print('  forward ported: %d' % len(composition.forwardports))
    my_print_upstream(composition.forwardports)

    print('New: %d' % len(flow.new))
    composition = PatchComposition.from_commits(repo, patch_groups, date_selector, flow.new)
    print('  just new: %d' % len(composition.none))
    print_flow(repo, composition.none, verbosity=verbosity)
    print('  backports: %d' % len(composition.backports))
    my_print_upstream(composition.backports)
    print('  will go upstream in future: %d' % len(composition.forwardports))
    my_print_upstream(composition.forwardports)

    print('\n-----\n')
    print('In sum, %s consists of:' % stack_to)
    composition = PatchComposition.from_commits(repo, patch_groups, date_selector, stack_to.commit_hashes)
    print('  %d backports' % len(composition.backports))
    my_print_upstream(composition.backports)
    print('  %d future forwardports' % len(composition.forwardports))
    my_print_upstream(composition.forwardports)
    print('  %d remaining patches' % len(composition.none))
    print_flow(repo, composition.none, verbosity=verbosity)


def compare_stack_against_upstream(repo, patch_groups, date_selector, stack, verbosity=0):
    my_print_upstream = partial(print_upstream, repo, patch_groups, verbosity=verbosity, indent=2)

    composition = PatchComposition.from_commits(repo, patch_groups, date_selector, stack.commit_hashes)
    print('%d backports went upstream' % len(composition.backports))
    my_print_upstream(composition.backports)
    print('%d forwardports went upstream' % len(composition.forwardports))
    my_print_upstream(composition.forwardports)
    print('%d must manually be ported' % len(composition.none))
    print_flow(repo, composition.none, verbosity=verbosity, indent=2)


def compare_stacks(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='Interactive Rating: Rate evaluation results')
    parser.add_argument('-ds', dest='date_selector', default='SRD', choices=['SRD', 'CD'],
                        help='Date selector: Either Commit Date or Stack Release Date (default: %(default)s)')
    parser.add_argument('versions', metavar='version', nargs=2, help='versions to compare')
    parser.add_argument('-v', nargs='?', metavar='level', action=VAction,
                        dest='verbose', default=0, help='Verbosity level -v -vv -v 2')
    parser.set_defaults(R=True)
    args = parser.parse_args(argv)

    config.fail_no_patch_groups()
    psd = config.psd
    repo = config.repo
    patch_groups = config.patch_groups
    date_selector = get_date_selector(repo, psd, args.date_selector)

    stack_from = psd.get_stack_by_name(args.versions[0])

    if args.versions[1] == 'upstream':
        print('If you would now rebase %s to master, then:' % stack_from)
        compare_stack_against_upstream(repo, patch_groups, date_selector, stack_from, verbosity=args.verbose)
    else:
        stack_to = psd.get_stack_by_name(args.versions[1])
        print('\nComparing %s -> %s' % (stack_from, stack_to))
        compare_stack_against_stack(repo, patch_groups, date_selector, stack_from, stack_to, verbosity=args.verbose)

if __name__ == '__main__':
    config = sys.argv[1]
    compare_stacks(config, sys.argv[0], sys.argv[2:])
