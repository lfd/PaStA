#!/bin/bash

repo=$1

function show_hash {
	tmp=$(mktemp)
	git -C $repo --no-pager show --pretty=fuller $1 > $tmp
	echo $tmp
}

clear
lhs=$(show_hash $2)
rhs=$(show_hash $3)
pr -w 150 -m -t $lhs $rhs
rm $rhs $lhs
