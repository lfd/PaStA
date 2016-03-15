from git import Repo

from PaStA.Config import Config


config = Config('config')

repo = Repo(config.repo)

from PaStA.PatchStack import parse_patch_stack_definition
patch_stack_list = parse_patch_stack_definition(config.patch_stack_definition)
