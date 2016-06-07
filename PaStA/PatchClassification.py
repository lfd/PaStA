"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""


from functools import partial

from PaStA import get_commit


class PatchFlow:
    def __init__(self, invariant, dropped, new):
        """
        :param invariant: Patches, that remain the same between different releases of the stack
        :param dropped: Dropped patches
        :param new: New patches
        """
        self.invariant = invariant
        self.dropped = dropped
        self.new = new

    @staticmethod
    def compare_stack_releases(patch_groups, stack_a, stack_b):
        """
        Returns the flow of Patches between two arbitrary releases of the stack
        :param patch_groups: patch groups
        :param stack_a: "from"
        :param stack_b: "to"
        :return: PatchFlow object
        """

        def commit_hashes_to_group_ids(commit_hahes):
            retval = dict()
            for id, commit_hash in map(lambda x: (patch_groups.get_equivalence_id(x), x), commit_hahes):
                if id not in retval:
                    retval[id] = list()
                retval[id].append(commit_hash)
            return retval

        groups_a = commit_hashes_to_group_ids(stack_a.commit_hashes)
        groups_b = commit_hashes_to_group_ids(stack_b.commit_hashes)

        invariant = dict()
        dropped = []
        new = list(stack_b.commit_hashes)

        for group, hashes in groups_a.items():
            for hash in hashes:
                if group in groups_b:
                    dests = groups_b[group]
                    invariant[hash] = dests
                    for dest in dests:
                        if dest in new:
                            new.remove(dest)
                else:
                    dropped.append(hash)

        # linearise invariant to bring it in right order
        linearised = []
        for hash in stack_a.commit_hashes:
            if hash in invariant:
                linearised.append((hash, invariant[hash]))
        invariant = linearised

        return PatchFlow(invariant, dropped, new)


class PatchComposition:
    def __init__(self, backports, forwardports, none):
        """
        :param backports: Patches, that are classified as backports
        :param forwardports: Patches, that are classified as forwardports
        :param none: Remaining patches
        """
        self.backports = backports
        self.forwardports = forwardports
        self.none = none

    @staticmethod
    def is_forwardport(patch_groups, date_selector, commit):
        """
        Given a commit hash on the patch stack, is_forwardport returns True, if the commit is a forward port,
        False, if it is a backport and None if it has no upstream candidate
        :param patch_groups: patch groups
        :param date_selector: date_selector
        :param commit: commit on the patch stack
        :return:
        """
        id = patch_groups.get_equivalence_id(commit)
        return PatchComposition.is_forwardport_by_id(patch_groups, date_selector, id)

    @staticmethod
    def is_forwardport_by_id(patch_groups, date_selector, id):
        if patch_groups.get_property_by_id(id) is None:
            return None

        upstream = patch_groups.get_property_by_id(id)

        first_stack_occurence = min(map(date_selector, patch_groups.get_commit_hashes_by_id(id)))
        upstream_commit_date = get_commit(upstream).commit_date

        delta = upstream_commit_date - first_stack_occurence

        if delta.days < -1:
            return False
        else:
            return True

    @staticmethod
    def from_commits(patch_groups, date_selector, commits):
        # Bind parameters to function
        classifier = partial(PatchComposition.is_forwardport, patch_groups, date_selector)
        description = [(lambda x: (x, classifier(x)))(x) for x in commits]

        forwardports = [x[0] for x in description if x[1] is True]
        backports = [x[0] for x in description if x[1] is False]
        none = [x[0] for x in description if x[1] is None]

        return PatchComposition(backports, forwardports, none)
