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
from logging import getLogger

from .Cluster import Cluster
from .Repository import Repository
from .PatchStack import PatchStackDefinition

log = getLogger(__name__[-15:])


class Thresholds:
    def __init__(self, autoaccept, interactive, diff_lines_ratio,
                 heading, filename, message_diff_weight,
                 author_date_interval):
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
        :param author_date_interval: Used for preevaluation: Two patches will only
               be considered for comparison, if the difference of their
               author_dates is within patch_time_window days. A value of 0
               means infinite days.
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
        # dlr
        self.diff_lines_ratio = diff_lines_ratio
        # ptw
        self.author_date_interval = author_date_interval


class Config:
    D_RESOURCES = 'resources'
    D_COMMON = join(D_RESOURCES, 'common')

    D_PROJECT_ROOT = join(D_RESOURCES, '%s')

    # Configuration file containing default parameters
    DEFAULT_CONFIG = join(D_COMMON, 'default.cfg')
    BLACKLIST_LOCATION = join(D_COMMON, 'blacklists')

    def __init__(self, project):
        self._project_root = realpath(Config.D_PROJECT_ROOT % project)
        self._config_file = join(self._project_root, 'config')

        if not isfile(Config.DEFAULT_CONFIG):
            raise FileNotFoundError('Default config file \'%s\' not found' %
                                    Config.DEFAULT_CONFIG)

        if not isfile(self._config_file):
            raise FileNotFoundError('Config file \'%s\' not found' %
                                    project)
        else:
            log.info('Active configuration: %s' % project)

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
        self.repo_location = join(self._project_root, self.repo_location)
        self.repo = Repository(self.repo_location)

        self.upstream_range = pasta.get('UPSTREAM')
        if not self.upstream_range:
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
        self.d_mbox = path('MBOX')

        # commit hash blacklist
        self.upstream_blacklist = pasta.get('UPSTREAM_BLACKLIST')

        # analysis results
        self.d_false_positives = path('FALSE_POSTITIVES')

        self.f_pasta_result = path('PASTA_RESULT')
        self.f_mbox_result = path('MBOX_RESULT')

        self.f_commit_description = path('COMMIT_DESCRIPTION')

        self.f_upstream_duration = path('UPSTREAM_DURATION')

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
                                     float(pasta.get('MESSAGE_DIFF_WEIGHT')),
                                     int(pasta.get('AUTHOR_DATE_INTERVAL')))

        self.patch_stack_definition = \
            PatchStackDefinition.parse_definition_file(self)

    def load_patch_groups(self, is_mbox, must_exist=False, f_patch_groups=None):
        if f_patch_groups is None:
            f_patch_groups = self.f_pasta_result
            if is_mbox:
                self.repo.register_mailbox(self.d_mbox)
                f_patch_groups = self.f_mbox_result

        if must_exist:
            Config.fail_result_not_exists(f_patch_groups)

        patch_groups = Cluster.from_file(f_patch_groups, must_exist=must_exist)

        return f_patch_groups, patch_groups

    @staticmethod
    def fail_result_not_exists(filename):
        if not isfile(filename):
            log.error('Result %s not existent' % filename)
            log.error('Run \'pasta analyse init\' first.')
            quit(-1)

    @property
    def psd(self):
        return self.patch_stack_definition
