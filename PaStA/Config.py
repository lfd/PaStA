import configparser
import os


class Thresholds:
    def __init__(self, autoaccept, interactive, diff_length):
        self.autoaccept = autoaccept
        self.interactive = interactive
        self.diff_length = diff_length


class Config:

    # Configuration file containing default parameters
    DEFAULT_CONFIG = 'PaStA-resources/common/default.cfg'
    BLACKLIST_LOCATION = 'PaStA-resources/common/blacklists'

    class CommitLocation:
        DATE = 'dates/'
        AUTHOR_EMAIL = 'author_emails/'
        DIFFS = 'diffs/'
        MESSAGES = 'messages/'

        def __init__(self, log_location):
            self.date = os.path.join(log_location, Config.CommitLocation.DATE)
            self.author_email = os.path.join(log_location, Config.CommitLocation.AUTHOR_EMAIL)
            self.diffs = os.path.join(log_location, Config.CommitLocation.DIFFS)
            self.messages = os.path.join(log_location, Config.CommitLocation.MESSAGES)

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

        self.repo = pasta.get('REPO')
        if not self.repo:
            raise RuntimeError('Location of repository not found')
        self.repo = os.path.join(self._project_root, self.repo)

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
        self.log_location = os.path.join(self._project_root, pasta.get('LOG'))
        self.commit = Config.CommitLocation(self.log_location)
        self.R_resources = os.path.join(self._project_root, pasta.get('R_RESOURCES'))
        self.upstream_blacklist = pasta.get('UPSTREAM_BLACKLIST')
        if self.upstream_blacklist:
            self.upstream_blacklist = os.path.join(Config.BLACKLIST_LOCATION, self.upstream_blacklist)

        self.thresholds = Thresholds(pasta.get('AUTOACCEPT_THRESHOLD'),
                                     pasta.get('INTERACTIVE_THRESHOLD'),
                                     pasta.get('DIFF_LENGTH_RATIO'))
