#! /bin/bash

# Author:
#   Rohit Sarkar <rohitsarkar5398@gmail.com>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

set -e

if [ $# -ne 3 ]; then
	echo "Usage: patchwork_integration_test.sh <path-to-public-inbox> <timestamp> <list-address>"
	echo "Only mails in public inbox since the given <timestamp> will be considered"
	exit 1
fi

# Project settings
PUBIN_PATH=$1
SINCE=$2
LIST_ADDR=$3
PROJECT=$(echo $LIST_ADDR | sed -e 's/\(.*\)@.*/\1/')

# Paths
PATCHWORK=/tmp/patchwork
MBOX=$PATCHWORK/$LIST_ADDR.mbox
DUMPED_MBOX=$PATCHWORK/$PROJECT.mbox
INITIAL_MBOX=$PATCHWORK/$PROJECT-initial.mbox

TOOLS=$(dirname $(realpath ${BASH_SOURCE[0]}))
PASTA=$(realpath $TOOLS/..)

PATCHWORK_REPO="https://github.com/lfd/patchwork.git"

INITIAL_IMPORT_SIZE=50 # Percentage of mbox to be imported as a raw mbox

clean_up() {
	1>/dev/null 2>&1 docker rm -f pasta-patchwork
}

trap clean_up EXIT

get_config() {
	# Get a minimal config for PaStA
	# For api imports we keep the intial archive field empty
	initial_archive=""
	if [ $1 = "mbox" ]
	then
		initial_archive=$INITIAL_MBOX
	fi
	config=$(cat <<-END
		[PaStA]
		MODE = "mbox"
		UPSTREAM = "HEAD^..HEAD"

		INTERACTIVE_THRESHOLD = 0.82
		AUTOACCEPT_THRESHOLD = 0.82
		DIFF_LINES_RATIO = 0.7
		HEADING_THRESHOLD = 0.6
		FILENAME_THRESHOLD = 0.95

		[mbox]
		[mbox.patchwork]
		url='http://localhost:8000/api/'
		projects = [{id=$project_id, initial_archive="$initial_archive", list_email="$LIST_ADDR"}]
		END
	)
}

if [ ! -d $PATCHWORK ]; then
	git clone -b pasta-patchwork-integration $PATCHWORK_REPO $PATCHWORK
fi

if [ ! -f $MBOX ]; then
	echo "Converting public inbox to mbox..."
	$TOOLS/pubin2mbox.sh $PUBIN_PATH $SINCE > $MBOX
fi

# Preparation for building the patchwork container
cd $PATCHWORK
echo -e "UID=$UID\nGID=$(id -g)" > .env

# Build the patchwork container
docker-compose build

# The pasta-setup script is used to import a raw mbox into patchwork and then
# subsequently export the mbox from patchwork. This is done to obtain
# the patch ids that patchwork associates with patches.

if [ ! -f $DUMPED_MBOX ]; then
	docker-compose run --rm web ./pasta-setup.sh $LIST_ADDR
fi

# the pasta-setup script also generates a file "project_id" that contains the
# project id of the patchwork project created.
project_id=$(cat project_id)

if [ ! -f $INITIAL_MBOX ]; then
	# Get the number of lines in the first INITIAL_IMPORT_SIZE % of the mbox
	num_lines=$(( $(wc -l $DUMPED_MBOX | cut -d" " -f 1) * $INITIAL_IMPORT_SIZE / 100 ))
	head -n $num_lines $DUMPED_MBOX > $INITIAL_MBOX
fi

echo Starting Patchwork web server...
docker-compose run -d --name pasta-patchwork -p 8000:8000 web ./manage.py runserver 0.0.0.0:8000

cd $PASTA

get_config mbox
echo "$config" > resources/linux/config
./pasta set_config linux

# remove existing caches and invalid index
./pasta sync -noup -clear all
rm -fv resources/linux/resources/mbox/{invalid, patchwork}
rm -fv resources/linux/resources/mbox/index/patchwork.*

#initial import
./pasta sync -mbox -create downstream

get_config api
echo "$config" > resources/linux/config

# api import
./pasta sync -mbox -create downstream

./pasta analyse rep
./pasta rate
./pasta form_patchwork_relations

mv resources/linux/resources/patch-groups-patchwork $PATCHWORK
cd $PATCHWORK
docker-compose run --rm web ./manage.py replacerelations patch-groups-patchwork
