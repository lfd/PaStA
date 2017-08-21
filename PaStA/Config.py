"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import configparser
from os.path import join, dirname, realpath, isfile, isdir
from os import makedirs

from .Repository import Repository
from .PatchStack import PatchStackDefinition


class Thresholds:
    def __init__(self, autoaccept, interactive, diff_lines_ratio,
                 heading, filename, message_diff_weight):
        """
        :param autoaccept: Auto accept threshold. Ratings with at least this
               threshold will automatically be accepted.
        :param interactive: Ratings with at least this threshold are presented
               to the user for interactive rating.  Ratings below this threshold
               will automatically be discarded.
        :param diff_lines_ratio: Minimum ratio of shorter diff / longer diff
        :param heading: Minimum similarity rating of the section heading of a
               diff
        :param filename: Minimum similarity of two filenames for being evaluated
               (files in a repo may move).
        :param message_diff_weight: heuristic factor of message rating to diff
               rating
        """

        # t_a
        self.autoaccept = autoaccept
        # t_i
        self.interactive = interactive
        # t_h
        self.heading = heading
        # t_f
        self.filename = filename
        # w
        self.message_diff_weight = message_diff_weight

        self.diff_lines_ratio = diff_lines_ratio


class Config:

    # Configuration file containing default parameters
    DEFAULT_CONFIG = 'PaStA-resources/common/default.cfg'
    BLACKLIST_LOCATION = 'PaStA-resources/common/blacklists'

    def __init__(self, config_file):
        self._project_root = dirname(realpath(config_file))
        self._config_file = config_file

        if not isfile(Config.DEFAULT_CONFIG):
            raise FileNotFoundError('Default config file \'%s\' not found' %
                                    Config.DEFAULT_CONFIG)

        if not isfile(config_file):
            raise FileNotFoundError('Config file \'%s\' not found' %
                                    config_file)

        cfg = configparser.ConfigParser()
        cfg.read([Config.DEFAULT_CONFIG, self._config_file])
        pasta = cfg['PaStA']

        # Obligatory values
        self.project_name = pasta.get('PROJECT_NAME')
        if not self.project_name:
            raise RuntimeError('Project name not found')

        self.repo_location = pasta.get('REPO')
        if not self.repo_location:
            raise RuntimeError('Location of repository not found')
        self.repo_location = join(self._project_root,
                                          self.repo_location)
        self.repo = Repository(self.repo_location)

        self.upstream_range = (pasta.get('UPSTREAM_MIN'),
                               pasta.get('UPSTREAM_MAX'))
        if not all(self.upstream_range):
            raise RuntimeError('Please provide a valid upstream range in your '
                               'config')

        def option(name):
            return pasta.get(name)

        def path(name):
            return join(self._project_root, option(name))

        # parse locations, those will fallback to default values
        self.f_patch_stack_definition = path('PATCH_STACK_DEFINITION')

        # commit hash files and mailbox ID files
        self.d_stack_hashes = path('STACK_HASHES')
        if not isdir(self.d_stack_hashes):
            makedirs(self.d_stack_hashes)

        self.f_upstream_hashes = join(self.d_stack_hashes, 'upstream')
        self.d_mailbox_split = path('MBOX_SPLIT')
        self.f_mailbox_index = join(self.d_mailbox_split, 'index')
        self.f_mailbox = path('MBOX')

        # register mailbox to repository, if existent
        self.has_mailbox = self.repo.register_mailbox(self.d_mailbox_split,
                                                      self.f_mailbox_index,
                                                      self.f_mailbox)

        # commit hash blacklist
        self.upstream_blacklist = pasta.get('UPSTREAM_BLACKLIST')

        # analysis results
        self.f_similar_patches = path('SIMILAR_PATCHES')
        self.f_similar_upstream = path('SIMILAR_UPSTREAM')
        self.f_similar_mailbox = path('SIMILAR_MAILBOX')
        self.d_false_positives = path('FALSE_POSTITIVES')
        self.f_patch_groups = path('PATCH_GROUPS')

        self.f_commit_description = path('COMMIT_DESCRIPTION')

        # pkl commit cache (ccache) and result files
        self.f_evaluation_result = path('EVALUATION_RESULT')
        self.f_ccache_stack = path('COMMIT_CACHE_STACK')
        self.f_ccache_upstream = path('COMMIT_CACHE_UPSTREAM')
        self.f_ccache_mbox = path('COMMIT_CACHE_MBOX')

        # R location
        self.R_resources = path('R_RESOURCES')

        # mailbox parameters
        self.mbox_mindate = pasta.get('MBOX_MINDATE')
        self.mbox_maxdate = pasta.get('MBOX_MAXDATE')

        if self.upstream_blacklist:
            self.upstream_blacklist = join(Config.BLACKLIST_LOCATION,
                                           self.upstream_blacklist)

        # default thresholds
        self.thresholds = Thresholds(float(pasta.get('AUTOACCEPT_THRESHOLD')),
                                     float(pasta.get('INTERACTIVE_THRESHOLD')),
                                     float(pasta.get('DIFF_LINES_RATIO')),
                                     float(pasta.get('HEADING_THRESHOLD')),
                                     float(pasta.get('FILENAME_THRESHOLD')),
                                     float(pasta.get('MESSAGE_DIFF_WEIGHT')))

        self.patch_stack_definition = \
            PatchStackDefinition.parse_definition_file(self)

    def fail_no_mailbox(self):
        if self.has_mailbox is False:
            print("Mailbox '%s' not configured or not available. "
                  "Check your config." % self.f_mailbox)
            quit(-1)

    @property
    def psd(self):
        return self.patch_stack_definition
