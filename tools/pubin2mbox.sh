#! /bin/bash

# Author:
#   Rohit Sarkar <rohitsarkar5398@gmail.com>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

pubin=$1
since=$2

git -C $pubin --no-pager log --pretty=format:%H --since=$since --reverse | \
	xargs -n 1 -I {} bash -c "
			git -C $pubin --no-pager show --no-patch --pretty=format:'From %ae %ad' {};
			echo;
			git -C $pubin --no-pager show {}:m;
			echo;
			"
