from git import Repo

from PaStA.PatchStack import parse_patch_stack_definition

from config import *

repo = Repo(REPO_LOCATION)
patch_stack_list = parse_patch_stack_definition(PATCH_STACK_DEFINITION)
