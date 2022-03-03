#!/usr/bin/bash

set -e

for project in linux u-boot qemu xen
do
	cd "resources/$project/repo"
	git fetch --all
	if [[ $project == "linux" ]]; then
		versions=$(git tag --list | grep -E "(^v2\.6\.39$|^v[0-9]{1,2}\.[0-9]{1,3}$)" | sort -V)
	elif [[ $project == "u-boot" ]]; then
		versions=$(git tag --list | grep -E "^v20[12]" | grep "^v20[12]" | grep -v "^v201[0123]" | grep -v "^v2014\.0[147]" | grep -v "v2014\.10-rc1" | sort -V)
	elif [[ $project == "xen" ]]; then
		versions=$(git tag --list | grep -v "^3" | grep -v "^\(RELEASE-\)\?4\.0\." | grep -v "RELEASE-[23]" | grep -P "^\d|R" | sort -V)
	elif [[ $project == "qemu" ]]; then
		versions=$(git tag --list | grep -v "^release" | grep -v "^v0\.[123456789]\." | grep -v "^v0\.1[0123]\." | grep -v "initial")
	fi
	
	echo "Project; Version; No-Mtrs; LoC; No-Sections; No-Clusters"
	for version in $versions; do
	        git checkout $version > /dev/null 2>&1
	        mtrs=$(cat MAINTAINERS | grep -a "^M:" | sort | uniq | wc -l)
	        loc=$(find . -type f -not -regex '\./\.git.*'|xargs cat|wc -l)
		sections=$(cat ../resources/maintainers_section_graph/$version.csv | cut -d, -f1 | uniq | wc -l)
		clusters=$(cat ../resources/maintainers_cluster/$version.csv | cut -d, -f1 | uniq | wc -l)
		echo "$project; $version; $mtrs; $loc; $(($sections-1)); $(($clusters-1))"
	done
	cd -
done


