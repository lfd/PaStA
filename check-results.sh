#!/bin/bash

upstream_dir="./upstream-results"

repo="./linux"

function show_hash {
	tmp=$(mktemp)
	git -C $repo --no-pager show $1 > $tmp
	echo $tmp
}

cntr=0
for i in $upstream_dir/*
do
	orig_hash=$(basename $i)
	cand_hashes=$(cat $i)

	lhs=$(show_hash $orig_hash)
	while read -r line; do
		cand_hash=$(echo $line | awk '{print $1}')
		rating=$(echo $line | awk '{print $2}')
		msg=$(echo $line | cut -f 3- -d ' ')
		rhs=$(show_hash $cand_hash)
		pr -w 150 -m -t $lhs $rhs
		echo $cntr
		rm $rhs
		echo "rating: $rating -- $msg ($orig_hash <-> $cand_hash)"
		read -n1 -p "Yay or nay?" yn < /dev/tty
		echo
		case $yn in
			y|Y) cntr=$[cntr + 1]
				 break
				 ;;
			n|N) ;;
			*)   ;;
		esac
	done <<< "$cand_hashes"
	rm $lhs
done

echo $cntr
