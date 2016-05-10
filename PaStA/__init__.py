from pygit2 import Repository

from PaStA.Config import Config

config = Config('config')

repo = Repository(config.repo_location)

from PaStA.PatchStack import PatchStackDefinition
patch_stack_definition = PatchStackDefinition.parse_definition_file(config.patch_stack_definition)
