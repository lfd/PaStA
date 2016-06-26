"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .Util import format_date_ymd


class Export:
    def __init__(self, repo, patch_stack_definition):
        self.repo = repo
        self.psd = patch_stack_definition

    def release_dates(self, mainline_release_dates_filename, stack_release_dates_filename):
        stacks = dict()
        base = dict()

        for group_name, stacks_in_group in self.psd.iter_groups():
            for stack in stacks_in_group:
                stacks[stack.stack_version] = group_name, stack.stack_release_date
                base[stack.base_version] = stack.base_release_date

        with open(mainline_release_dates_filename, 'w') as f:
            f.write('Version ReleaseDate\n')
            for version, date in base.items():
                f.write('%s %s\n' %
                        (version, format_date_ymd(date)))

        with open(stack_release_dates_filename, 'w') as f:
            f.write('VersionGroup Version ReleaseDate\n')
            for version, (group, date) in stacks.items():
                f.write('%s %s %s\n' % (group,
                                        version,
                                        format_date_ymd(date)))

    def sorted_release_names(self, release_sort_filename):
        with open(release_sort_filename, 'w') as f:
            f.write('VersionGroup Version\n')
            for version_group, stacks in self.psd.iter_groups():
                for stack in stacks:
                    f.write('%s %s\n' % (version_group, stack.stack_version))

    def patch_groups(self, upstream_filename, patches_filename, occurrence_filename, patch_groups, date_selector):
        psd = self.psd
        upstream = open(upstream_filename, 'w')
        patches = open(patches_filename, 'w')
        occurrence = open(occurrence_filename, 'w')

        # Write CSV Headers
        upstream.write('PatchGroup UpstreamHash UpstreamCommitDate FirstStackOccurence\n')
        patches.write('PatchGroup CommitHash StackVersion BaseVersion\n')
        occurrence.write('PatchGroup OldestVersion LatestVersion FirstReleasedIn LastReleasedIn\n')

        cntr = 0
        for group in patch_groups:
            cntr += 1

            # write stack patches
            for patch in group:
                stack_of_patch = psd.get_stack_of_commit(patch)
                stack_version = stack_of_patch.stack_version
                base_version = stack_of_patch.base_version
                patches.write('%d %s %s %s\n' % (cntr, patch, stack_version, base_version))

            # optional: write upstream information
            if group.property:
                commit = self.repo[group.property]

                first_stack_occurence = min(map(date_selector, group))

                upstream.write('%d %s %s %s\n' % (cntr,
                                                  commit.commit_hash,
                                                  format_date_ymd(commit.commit_date),
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
