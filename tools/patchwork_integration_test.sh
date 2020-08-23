#! /bin/bash

# Author:
#   Rohit Sarkar <rohitsarkar5398@gmail.com>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

set -e
USAGE=$(cat <<-END
	$ ./patchwork_integration_test.sh <path-to-public-inbox> <timestamp> <list-address>
	Only mails in public inbox since the given <timestamp> will be considered
	END
	)
if [ $# -ne 3 ]
then
	echo -e "$USAGE"
	exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PUBIN_PATH=$1
SINCE=$2
LIST_ADDR=$3
MBOX=test-mbox.mbox
PROJECT=test-patchwork
INITIAL_IMPORT_SIZE=50 # Percentage of mbox to be imported as a raw mbox
INITIAL_IMPORT_MBOX=initial.mbox

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
		initial_archive=$INITIAL_IMPORT_MBOX
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

cd "$SCRIPT_DIR"

echo "Converting public inbox to mbox..."
./pubin2mbox.sh $PUBIN_PATH $SINCE > /tmp/$MBOX
if [ ! -d patchwork ]
then
	git clone https://github.com/rsarky/patchwork.git
fi

cp /tmp/$MBOX patchwork/

cd patchwork
git checkout pasta-patchwork-integration
echo "UID=$UID" > .env
echo "GID=`id -g`" >> .env
docker-compose build

# The pasta-setup script is used to import a raw mbox into patchwork and then
# subsequently export the mbox from patchwork. This is done to obtain 
# the patch ids that patchwork associates with patches.
docker-compose run --rm web ./pasta-setup.sh $MBOX $PROJECT

# the pasta-setup script also generates a file "project_id" that contains the
# project id of the patchwork project created.
project_id=$(cat project_id)
rm project_id

# Get the number of lines in the first INITIAL_IMPORT_SIZE % of the mbox
num_lines=$(( $(wc -l $PROJECT.mbox | cut -d" " -f 1) * $INITIAL_IMPORT_SIZE / 100 ))
head -n $num_lines $PROJECT.mbox > $INITIAL_IMPORT_MBOX
mkdir -p ../../resources/linux/resources/mbox/patchwork/
mv $INITIAL_IMPORT_MBOX $_

echo Starting Patchwork web server...
docker-compose run -d --name pasta-patchwork -p 8000:8000 web ./manage.py runserver 0.0.0.0:8000

cd ../..

get_config mbox
echo "$config" > resources/linux/config
./pasta set_config linux

# remove existing caches and invalid index
./pasta sync -noup -clear all
rm -f resources/linux/resources/mbox/invalid/*

#initial import
./pasta sync -mbox -create downstream

get_config api
echo "$config" > resources/linux/config
./pasta set_config linux

# api import
./pasta sync -mbox -create downstream

./pasta analyse rep
./pasta rate
./pasta form_patchwork_relations

mv resources/linux/resources/patch-groups-patchwork tools/patchwork/
cd $SCRIPT_DIR/patchwork
docker-compose run --rm web ./manage.py replacerelations patch-groups-patchwork
