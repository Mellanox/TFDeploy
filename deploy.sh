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


script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
work_dir=`mktemp -du`
base_port=$1
num_ps=$2
num_workers=$3
ips=(${@:4})
servers=""

# Get device mappings:
source mapping.sh
source mark_errors_and_warnings.sh

[[ -z $3 ]] && print_usage_and_exit
[[ -f tf_cnn_benchmarks.py ]] || {	echo "Error: tf_cnn_benchmarks.py is missing. deploy.sh should be run from tf_cnn_benchmarks folder."; exit 1; }
[[ -z $ips ]] && ips=(`hostname`)

num_ips=${#ips[@]}
device_id=0
port=$base_port
ps_hosts=()
worker_hosts=()
logs_dir=$script_dir/run_logs

rm -rf $logs_dir 
mkdir -p $logs_dir

function add_ip_to_cluster()
{
	ip=${ips[$ip_id]}
	host=$ip:$port
	ip_id=$((($ip_id + 1) % $num_ips))
	port=$(($port + 1))
}

function add_ps_to_cluster()
{
	add_ip_to_cluster
	if [[ -z $ps_hosts ]]; then
		ps_hosts=$host
	else
		ps_hosts="$ps_hosts,$host"
	fi
}

function add_worker_to_cluster()
{
	add_ip_to_cluster
	if [[ -z $worker_hosts ]]; then
		worker_hosts=$host
	else
		worker_hosts="$worker_hosts,$host"
	fi
}

function run_job()
{
	ip=$1
	job_name=$2
	task_id=$3
	if [[ $ip == "trex-00" ]]; then
		device=mlx5_2
	else
		device=mlx5_0
	fi
	get_server_of_ip $ip
	gnome-terminal --geometry=200x20 -x ssh $server "$work_dir/run_job.sh $job_name $task_id $ps_hosts $worker_hosts $device 2>&1 | tee $work_dir/${job_name}_${task_id}.log"
}

function output_log()
{
	tail -n 100 $1 | MarkErrorsAndWarnings
}

echo "IPs:"
for ip in "${ips[@]}"
do
	get_server_of_ip $ip
	echo " + $ip (Server: $server)"
	servers="$servers $server"
done

############
# Compile: #
############
echo "Building:"
echo "   See: $logs_dir/build.log"
[[ -z $TENSORFLOW_HOME ]] && TENSORFLOW_HOME=/root/tensorflow/
cd $TENSORFLOW_HOME
#bazel clean
bazel build --config=opt //tensorflow/tools/pip_package:build_pip_package >& $logs_dir/build.log
if [[ $? -ne 0 ]]; then output_log $logs_dir/build.log; error "Build failed."; fi
bazel-bin/tensorflow/tools/pip_package/build_pip_package $script_dir/tensorflow_pkg >> $logs_dir/build.log 2>&1
if [[ $? -ne 0 ]]; then output_log $logs_dir/build.log; error "Build failed."; fi
cd -

echo "Installing:"
for server in $servers
do
	echo " + $server..."
	ssh $server pip install --user --upgrade $script_dir/tensorflow_pkg/tensorflow-1.3.0* >& $logs_dir/install_$server.log
done
echo "Done."

#################
# COPY SCRIPTS: #
#################

echo "Copying scripts:"
echo "  + Source: $script_dir" 
echo "  + Destination: $work_dir" 

for ip in "${ips[@]}"
do
	get_server_of_ip $ip
	scp -r $script_dir $server:$work_dir > /dev/null
done

#########################
# INITIALIZE INSTANCES: #
#########################
echo "Creating PS:"
for (( c=0; c<$num_ps; c++ ))
do
	add_ps_to_cluster
	echo "  #$c: $host"
done

echo "Creating workers:"
for (( c=0; c<$num_workers; c++ ))
do
	add_worker_to_cluster
	echo "  #$c: $host"
done

########
# RUN: #
########
echo "Running:"
for (( c=0; c<$num_ps; c++ ))
do
	ip=`echo $ps_hosts | cut -d',' -f$(($c + 1)) | cut -d':' -f1`
	run_job $ip ps $c
done

for (( c=0; c<$num_workers; c++ ))
do
	ip=`echo $worker_hosts | cut -d',' -f$(($c + 1)) | cut -d':' -f1`
	run_job $ip worker $c
done

#################
# WAIT FOR END: #
#################
echo "Waiting for end..."
ip=`echo $worker_hosts | cut -d',' -f1 | cut -d':' -f1`
get_server_of_ip $ip
res=0
while [[ $res -eq 0 ]]
do
	res=`ssh $server [[ -f $work_dir/done.txt ]] && echo 1 || echo 0`
	sleep 1
done

echo "Copying logs..."
for server in $servers
do
	scp $server:$work_dir/*.log $logs_dir
done

echo "Done."
echo
echo "----------------------------------------------------------------"
cat $logs_dir/worker_0.log

############
# CLEANUP: #
############
for ip in "${ips[@]}"
do
	get_server_of_ip $ip
	ssh $server $work_dir/clean_host.sh
done
sleep 2

##################
# Close windows: #
##################
this_script=`basename $0`
echo "Closing windows..."
pids="`ps -ef | grep $work_dir/run_job.sh | grep -v " grep " | sed -e 's!^[a-zA-Z0-9]* *\([0-9]*\) .*!\1!g'`"

for pid in $pids; do
	echo " + Killing $pid..."
	kill -9 $pid
done
