#!/usr/bin/bash

set -e

echo "Project,Version,No-Mtrs,LoC,No-Sections,No-Clusters,No-CommitsLastVersion"
for project in linux qemu u-boot xen
do
	cd "resources/$project/repo"
	
	versions=$(git tag --merged origin/master | grep -v -- -rc)

	if [[ $project == "xen" ]]; then
		versions=$(git tag --merged origin/master)
	fi

	for version in $versions; do
		cluster="../resources/maintainers_cluster/$version.csv"
		if [ ! -f $cluster ]; then
			continue
		fi

		last_version=$(git tag --merged origin/master | grep -v -- -rc | grep $version -B 1 | head -n 1)

	        mtrs=$(git show $version:./MAINTAINERS | grep -a "^M:" | sort | uniq | wc -l)
		loc=$(git ls-tree -r $version | grep blob | awk '{print $3}' | xargs -P $(nproc) -n 1 git --no-pager show  | wc -l)
		sections=$(cat $cluster | tail -n +2 | wc -l)
		clusters=$(cat $cluster | cut -d, -f1 | tail -n +2 | sort | uniq | wc -l)
		#maintainers_changes_total=$(git log --no-merges --pretty=format:%an --follow -- MAINTAINERS | wc -l)
		#maintainers_changes_last_version=$(git log $last_version..$version --no-merges --pretty=format:%an --follow -- MAINTAINERS | wc -l)
		commits_last_version=$(git log $last_version..$version --no-merges --pretty=format:%h | wc -l)
		echo "$project,$version,$mtrs,$loc,$sections,$clusters,$commits_last_version"
	done
	cd -
done


