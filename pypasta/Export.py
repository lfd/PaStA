"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from multiprocessing import Pool, cpu_count

from .Util import format_date_ymd, get_first_upstream


# We need this global variable, as pygit2 Repository objects are not pickleable
_tmp_repo = None


def _diffstat_helper(args):
    version_name, base_commit, stack_commit = args
    diff = _tmp_repo.diff(base_commit, stack_commit)
    deletions = diff.stats.deletions
    insertions = diff.stats.insertions
    return version_name, deletions, insertions


class Export:
    def __init__(self, repo, patch_stack_definition):
        self.repo = repo
        self.psd = patch_stack_definition

    def diffstat(self, f_diffstat):
        # Get raw pygit2 Repo and store it in temporary global variable
        repo = self.repo.repo
        global _tmp_repo
        _tmp_repo = repo

        worklist = []
        for group_name, stacks_in_group in self.psd.iter_groups():
            for stack in stacks_in_group:
                base_version = stack.base_name
                stack_branch = stack.stack_name

                base_ref = 'refs/tags/' + base_version
                stack_ref = 'refs/remotes/' + stack_branch

                base_commit = str(repo[repo.lookup_reference(base_ref).target].target)
                stack_commit = str(repo.lookup_reference(stack_ref).target)

                worklist.append((stack.stack_version, base_commit, stack_commit))

        p = Pool(cpu_count())
        results = p.map(_diffstat_helper, worklist)
        p.close()
        p.join()
        _tmp_repo = None

        with open(f_diffstat, 'w') as f:
            f.write('Version Deletions Insertions\n')
            for version_name, deletions, insertions in results:
                    f.write('%s %d %d\n' % (version_name, deletions, insertions))

    def release_dates(self, f_mainline_release_dates, f_stack_release_dates):
        stacks = dict()
        base = dict()

        for group_name, stacks_in_group in self.psd.iter_groups():
            for stack in stacks_in_group:
                stacks[stack.stack_version] = group_name, stack.stack_release_date
                base[stack.base_version] = stack.base_release_date

        with open(f_mainline_release_dates, 'w') as f:
            f.write('Version ReleaseDate\n')
            for version, date in base.items():
                f.write('%s %s\n' %
                        (version, format_date_ymd(date)))

        with open(f_stack_release_dates, 'w') as f:
            f.write('VersionGroup Version ReleaseDate\n')
            for version, (group, date) in stacks.items():
                f.write('%s %s %s\n' % (group,
                                        version,
                                        format_date_ymd(date)))

    def sorted_release_names(self, f_release_sort):
        with open(f_release_sort, 'w') as f:
            f.write('VersionGroup Version\n')
            for version_group, stacks in self.psd.iter_groups():
                for stack in stacks:
                    f.write('%s %s\n' % (version_group, stack.stack_version))

    def patch_groups(self, f_upstream, f_patches, f_occurrence,
                     cluster, date_selector):
        psd = self.psd
        upstream = open(f_upstream, 'w')
        patches = open(f_patches, 'w')
        occurrence = open(f_occurrence, 'w')

        # Write CSV Headers
        upstream.write('PatchGroup UpstreamHash UpstreamCommitDate FirstStackOccurence\n')
        patches.write('PatchGroup CommitHash StackVersion BaseVersion\n')
        occurrence.write('PatchGroup OldestVersion LatestVersion FirstReleasedIn LastReleasedIn\n')

        cntr = 0
        for group in cluster.iter_untagged():
            group = list(group)
            cntr += 1

            # write stack patches
            for patch in group:
                stack_of_patch = psd.get_stack_of_commit(patch)
                stack_version = stack_of_patch.stack_version
                base_version = stack_of_patch.base_version
                patches.write('%d %s %s %s\n' % (cntr, patch, stack_version, base_version))

            # optional: write upstream information
            commit = get_first_upstream(self.repo, cluster, group[0])
            if commit:
                commit = self.repo[commit]
                first_stack_occurence = min(map(date_selector, group))

                upstream.write('%d %s %s %s\n' % (cntr,
                                                  commit.identifier,
                                                  format_date_ymd(commit.commit.date),
                                                  format_date_ymd(first_stack_occurence)))

            # Patch occurrence
            latest_version = oldest_version = psd.get_stack_of_commit(group[0])
            first_released = last_released = date_selector(group[0]), psd.get_stack_of_commit(group[0])

            for patch in group[1:]:
                # Get stack of current patch
                stack = psd.get_stack_of_commit(patch)

                # Check latest version
                if psd.is_stack_version_greater(stack, latest_version):
                    latest_version = stack

                # Check oldest version
                if not psd.is_stack_version_greater(stack, oldest_version):
                    oldest_version = stack

                # Check first released in
                if date_selector(patch) < first_released[0]:
                    first_released = date_selector(patch), stack

                # Check last released in
                if date_selector(patch) > last_released[0]:
                    last_released = date_selector(patch), stack

            latest_version = latest_version.stack_version
            oldest_version = oldest_version.stack_version

            first_released = first_released[1].stack_version
            last_released = last_released[1].stack_version

            occurrence.write('%d %s %s %s %s\n' % (cntr,
                                                   oldest_version, latest_version,
                                                   first_released, last_released))

        upstream.close()
        patches.close()
        occurrence.close()
