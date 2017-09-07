#!/bin/bash

function print_usage()
{
	echo "Usage: `basename $0` <base-port> <num_ps> <num_workers> [server1 server2 ...]"
	echo "   The script will round-robin the PS between availble servers."
	echo "   If no servers spefied, localhost will be used."
	echo "   Examples:"
	echo "       `basename $0` 10000 1 2 trex-00 trex-02"
	echo "       `basename $0` 10000 1 2"
}

function print_usage_and_exit()
{
	print_usage
	exit 1
}

base_port=$1
num_ps=$2
num_workers=$3
hosts=(${@:4})

[[ -z $3 ]] && print_usage_and_exit

[[ -z $hosts ]] && hosts=(`hostname`)

num_hosts=${#hosts[@]}
host_id=0
port=$base_port
ps_hosts=()
worker_hosts=()

function new_host()
{
	host=${hosts[$host_id]}:$port
	if [[ $host == "localhost" ]]; then
		host=`hostname`
	fi
	host_id=$((($host_id + 1) % $num_hosts))
	port=$(($port + 1))
}

function new_ps_host()
{
	new_host
	if [[ -z $ps_hosts ]]; then
		ps_hosts=$host
	else
		ps_hosts="$ps_hosts,$host"
	fi
}

function new_worker_host()
{
	new_host
	if [[ -z $worker_hosts ]]; then
		worker_hosts=$host
	else
		worker_hosts="$worker_hosts,$host"
	fi
}


function run_job()
{
#	if [[ $1 == "localhost" ]]; then
#		gnome-terminal -x sh -c "$dst_dir/run_job.sh $2 $c $ps_hosts $worker_hosts; bash"
#	else
		gnome-terminal -x ssh $1 "$dst_dir/run_job.sh $2 $c $ps_hosts $worker_hosts; bash"
#	fi
}

#################
# COPY SCRIPTS: #
#################
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
dst_dir=`mktemp -du`

echo "Copying scripts:"
echo "  + Source: $script_dir" 
echo "  + Destination: $dst_dir" 

for host in "${hosts[@]}"
do
	scp -r $script_dir $host:$dst_dir > /dev/null
done

#########################
# INITIALIZE INSTANCES: #
#########################
echo "Creating PS:"
for (( c=0; c<$num_ps; c++ ))
do
	new_ps_host
	echo "  #$c: $host"
done

echo "Creating workers:"
for (( c=0; c<$num_workers; c++ ))
do
	new_worker_host
	echo "  #$c: $host"
done

########
# RUN: #
########
for (( c=0; c<$num_ps; c++ ))
do
	my_host=`echo $ps_hosts | cut -d',' -f$(($c + 1)) | cut -d':' -f1`
	run_job $my_host ps
done
for (( c=0; c<$num_workers; c++ ))
do
	my_host=`echo $worker_hosts | cut -d',' -f$(($c + 1)) | cut -d':' -f1`
	run_job $my_host worker
done

#################
# WAIT FOR END: #
#################
echo "Waiting for end..."
host=`echo $worker_hosts | cut -d',' -f1 | cut -d':' -f1`
res=0
while [[ $res -eq 0 ]]
do
	res=`ssh $host [[ -f $dst_dir/done.txt ]] && echo 1 || echo 0`
	sleep 1
done

echo "Done."
ssh $host cat $dst_dir/run_logs/worker_0.log

############
# CLEANUP: #
############
for host in "${hosts[@]}"
do
	scp $host:$dst_dir/run_logs/* run_logs
	ssh $host $dst_dir/clean_host.sh
done
sleep 2

##################
# Close windows: #
##################
this_script=`basename $0`
echo "Closing windows..."
pids="`ps -ef | grep $dst_dir/run_job.sh | grep -v " grep " | sed -e 's!^[a-zA-Z0-9]* *\([0-9]*\) .*!\1!g'`"

for pid in $pids; do
	echo " + Killing $pid..."
	kill -9 $pid
done
