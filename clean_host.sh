#!/bin/bash

dst_dir=`dirname $0`
this_script=`basename $0`

echo "Cleaning `hostname`:$dst_dir"
pids="`ps -ef | grep $dst_dir | grep python | sed -e 's!^[a-zA-Z0-9]* *\([0-9]*\) .*!\1!g'`"

for pid in $pids; do
	echo " + Killing $pid..."
	kill -9 $pid
done
	
rm -rf $dst_dir
