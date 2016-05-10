import configparser
import os


class Thresholds:
    def __init__(self, autoaccept, interactive, diff_lines_ratio,
                 heading, message_diff_weight):
        """
        :param autoaccept: Auto accept threshold. Ratings with at least this threshold will automatically be accepted.
        :param interactive: Ratings with at least this threshold are presented to the user for interactive rating.
               Ratings below this threshold will automatically be discarded.
        :param diff_lines_ratio: Minimum ratio of shorter diff / longer diff
        :param heading: Minimung similarity rating of the section heading of a diff
        :param message_diff_weight: heuristic factor of message rating to diff rating
        """

        # t_a
        self.autoaccept = autoaccept
        # t_i
        self.interactive = interactive
        # t_h
        self.heading = heading
        # w
        self.message_diff_weight = message_diff_weight

        self.diff_lines_ratio = diff_lines_ratio

class Config:

    # Configuration file containing default parameters
    DEFAULT_CONFIG = 'PaStA-resources/common/default.cfg'
    BLACKLIST_LOCATION = 'PaStA-resources/common/blacklists'

    def __init__(self, config_file):
        self._project_root = os.path.dirname(os.path.realpath(config_file))
        self._config_file = config_file

        if not os.path.isfile(Config.DEFAULT_CONFIG):
            raise FileNotFoundError('Default config file \'%s\' not found' % Config.DEFAULT_CONFIG)

        if not os.path.isfile(config_file):
            raise FileNotFoundError('Config file \'%s\' not found' % config_file)

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
        self.repo_location = os.path.join(self._project_root, self.repo_location)

        self.upstream_range = pasta.get('UPSTREAM_MIN'), pasta.get('UPSTREAM_MAX')
        if not all(self.upstream_range):
            raise RuntimeError('Please provide a valid upstream range in your config')

        # Parse locations, those will fallback to default values
        self.patch_stack_definition = os.path.join(self._project_root, pasta.get('PATCH_STACK_DEFINITION'))
        self.stack_hashes = os.path.join(self._project_root, pasta.get('STACK_HASHES'))
        self.similar_patches = os.path.join(self._project_root, pasta.get('SIMILAR_PATCHES'))
        self.similar_upstream = os.path.join(self._project_root, pasta.get('SIMILAR_UPSTREAM'))
        self.false_positives = os.path.join(self._project_root, pasta.get('FALSE_POSTITIVES'))
        self.patch_groups = os.path.join(self._project_root, pasta.get('PATCH_GROUPS'))
        self.commit_description = os.path.join(self._project_root, pasta.get('COMMIT_DESCRIPTION'))
        self.evaluation_result = os.path.join(self._project_root, pasta.get('EVALUATION_RESULT'))
        self.diffs_location = os.path.join(self._project_root, pasta.get('DIFFS'))
        self.R_resources = os.path.join(self._project_root, pasta.get('R_RESOURCES'))
        self.upstream_blacklist = pasta.get('UPSTREAM_BLACKLIST')
        if self.upstream_blacklist:
            self.upstream_blacklist = os.path.join(Config.BLACKLIST_LOCATION, self.upstream_blacklist)

        self.thresholds = Thresholds(float(pasta.get('AUTOACCEPT_THRESHOLD')),
                                     float(pasta.get('INTERACTIVE_THRESHOLD')),
                                     float(pasta.get('DIFF_LINES_RATIO')),
                                     float(pasta.get('HEADING_THRESHOLD')),
                                     float(pasta.get('MESSAGE_DIFF_WEIGHT')))
