#!/bin/bash

project=$(cat config)
res="resources/$project/resources"
bla="maintainers_cluster maintainers_cluster_fast_greedy maintainers_cluster_infomap maintainers_cluster_louvain"

# Anpassen gehen
#files=$(ls $res/$...etc etc)
for i in $bla; do
	target="$res/clusterings_$i"
	mkdir $target
	for csv in $res/$i/*.csv; do
		echo "working on $csv..."
		fse22-artifact/meiomei.py $csv > $target/$(basename -s .csv $csv).clustering
	done
done

for i in $bla; do
	files=$(ls $res/clusterings_$i)
	for f in $files; do
		echo $f
	done
done

for cluster_dir in $bla; do
	# angelegt und entleert
	echo -en > "$res/output_$cluster_dir.txt"
done

wt_files=$(ls $res/clusterings_maintainers_cluster)
for wt_file in $wt_files; do
	for cluster_dir in $bla; do
		target="$res/output_$cluster_dir.txt"
		## angelegt und entleert
		#echo -en > $target
		clustering_walktrap="$res/clusterings_maintainers_cluster/$wt_file"
		clustering_compare="$res/clusterings_$cluster_dir/$(basename $wt_file)"
		echo "Working on cluster compare file $clustering_compare"
		echo $(basename $clustering_compare) >> $target

		if ! [ -f $clustering_compare ]; then
			echo "file not existing, skipping"
			continue
		fi
		#./pasta compare_clusters -fm -pur -f $target $clustering_walktrap $clustering_compare
		./pasta compare_clusters -fm -pur $clustering_walktrap $clustering_compare >> $target
	done
done

for cluster_dir in $bla; do
	echo "Working on dir $cluster_dir"
	# Median und Mean printen
	echo "Fowlkes-Mallows: Mean/Median"
	cat "$res/output_$cluster_dir.txt" | grep Fowlkes-Mallows | cut -d : -f4 | cut -c 2- | awk '{sum += $1 n++} END { print sum/n; }'
	cat "$res/output_$cluster_dir.txt" | grep Fowlkes-Mallows | cut -d : -f4 | cut -c 2- | sort -n | awk ' { a[i++]=$1; } END { print a[int(i/2)]; }'
	echo "Purity: Mean/Median"
	cat "$res/output_$cluster_dir.txt" | grep Purity | cut -d : -f4 | cut -c 2- | awk '{sum += $1 n++} END { print sum/n; }'
	cat "$res/output_$cluster_dir.txt" | grep Purity | cut -d : -f4 | cut -c 2- | sort -n | awk ' { a[i++]=$1; } END { print a[int(i/2)]; }'
	echo "V-Measure: Mean/Median"
	cat "$res/output_$cluster_dir.txt" | grep V-measure | cut -d : -f4 | cut -c 2- | awk '{sum += $1 n++} END { print sum/n; }'
	cat "$res/output_$cluster_dir.txt" | grep V-measure | cut -d : -f4 | cut -c 2- | sort -n | awk ' { a[i++]=$1; } END { print a[int(i/2)]; }'
done
