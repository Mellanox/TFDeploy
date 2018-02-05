#!/bin/bash

function print_usage()
{
	echo "Usage: `basename $0` [OPTIONS] <benchmark> <base-port> <num_ps> <num_workers> [ip1 ip2 ...]"
	echo "   The script will round-robin the jobs between availble servers."
	echo "   If no servers spefied, localhost will be used."
	echo "   To run locally, pass num_ps=0."
	echo "   The script will automatically recognize the RDMA devices based on the ip addresses given."
	echo "   Important: Due to getopts limitiations, OPTIONS must come before the rest of the arguments."
	echo "   OPTIONS:"
	echo "       -m - model (trivial, inception3, resnet50, resnet152, vgg16)."
	echo "       -v - use grpc + verbs."
	echo "       -g - use grpc + gdr."
	echo "       -u - use grpc + ucx"
	echo "       -b - batch_size."
	echo "       -n - num gpus."
	echo "       -D - run with debug level (tensorflow). Levels (0, 1...). 'x' to run with gdb. 'p' to run with traceline."
	echo "       -c - compile and install tensorflow on all the given servers."
	echo "       -d - user comment (for benchmark results)."
	echo "       -r - data dir (default is syntetic data)."
	echo "       -s - don't open terminals (for regression tests)."
	echo "       -h - print this message and exit."
	echo "   Examples:"
	echo "       `basename $0` 10000 1 2 trex-00 trex-02"
	echo "       `basename $0` 10000 1 2"
}

function print_usage_and_exit()
{
	print_usage
	exit 1
}

#######################
# Read input options: #
#######################
num_gpus=0
batch_size=64
model=trivial
server_protocol=grpc
no_terminals_mode=0

while getopts ":m:cb:n:vguD:d:hr:s" opt
do
	case "$opt" in
	m)	model=$OPTARG;;
	v)	server_protocol="grpc+verbs";;
	g)	server_protocol="grpc+gdr";;
	u)	server_protocol="grpc+ucx";;
	b)	batch_size=$OPTARG;;
	n)	num_gpus=$OPTARG;;
	D)	log_level=$OPTARG;;
	d)	comment=$OPTARG;;
	r)	data_dir=$OPTARG;;
	s)	no_terminals_mode=1;;
	c)	compile=1;;
	h)	print_usage_and_exit;;
    \?) echo "Invalid option: -$OPTARG" >&2; return 1;;
    :)  echo "Option -$OPTARG requires an argument." >&2; return 1;;
  esac
done
shift "$((OPTIND-1))"


script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
work_dir=`mktemp -du`
benchmark=$1
base_port=$2
num_ps=$3
num_workers=$4
ips=(${@:5})
servers=""

# Get device mappings:
source mapping.sh
source mark_errors_and_warnings.sh

[[ -z $num_workers ]] && print_usage_and_exit
[[ ! -f $benchmark ]] && error "Benchmark \"$benchmark\" not found."
[[ $num_workers -eq 0 ]] && error "number of workers should be at least 1."
[[ -z $ips ]] && ips=(`hostname`)
[[ $no_terminals_mode -ne 1 ]] && [[ -z $DISPLAY ]] && error "DISPLAY is not set. You may need to reconnect with ssh -X."

benchmark_name=`basename $benchmark`
benchmark_dir=`dirname $benchmark`
num_ips=${#ips[@]}
device_id=0
port=$base_port
ps_hosts=()
worker_hosts=()
logs_base_dir=$HOME/TFDeploy_logs
logs_dir=$logs_base_dir/`date +%Y_%m_%d_%H_%M_%S`
if [[ ! -z $comment ]]
then
	logs_dir=${logs_dir}_`echo $comment | sed -e 's![^a-zA-Z0-9]\+!_!g'`
fi

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
	get_server_of_ip $ip
	if [[ $no_terminals_mode -ne 1 ]]
	then
		terminal_command="gnome-terminal --geometry=200x20 -x"
	fi
	$terminal_command ssh $server "TF_PS_HOSTS=$ps_hosts \
	                               TF_WORKER_HOSTS=$worker_hosts \
	                               TF_MODEL=$model \
	                               TF_NUM_GPUS=$num_gpus \
	                               TF_BATCH_SIZE=$batch_size \
	                               TF_SERVER_PROTOCOL=$server_protocol \
	                               TF_CPP_MIN_VLOG_LEVEL=$log_level \
	                               TF_DATA_DIR=$data_dir \
	                               TF_ADDITIONAL_FLAGS=$TF_ADDITIONAL_FLAGS \
	                               DEVICE_IP=$ip \
	                               BENCHMARK_NAME=$benchmark_name \
	                               $work_dir/run_job2.sh $job_name $task_id 2>&1 | tee $work_dir/${job_name}_${task_id}.log" &

	sleep 0.4 # Have windows open by order
}

function output_log()
{
	tail -n 100 $1 | MarkErrorsAndWarnings
}

#######################
# Kill old processes: #
#######################
echo "IPs:"
for ip in "${ips[@]}"
do
	get_server_of_ip $ip
	echo " + $ip (Server: $server)"
	servers="$servers $server"
	ssh $server "ps -ef | grep $benchmark_name | grep -v `basename $0` | grep -v $work_dir | sed -e \"s@$USER *\([0-9]\+\) .*@\1@g\" | xargs kill -9"
#	[[ $? -ne 0 ]] && error "Failed to stop running TF process."
done

############
# Compile: #
############
if [[ $compile -eq 1 ]]
then
	echo "Building:"
	echo "   See: $logs_dir/build.log"
	[[ -z $TENSORFLOW_HOME ]] && TENSORFLOW_HOME=/root/tensorflow/
	cd $TENSORFLOW_HOME
	if [[ $num_gpus -ne 0 ]]
	then
		CONFIG_CUDA="--config=cuda"
	fi
	if [[ ! -z $TENSORFLOW_BUILD_FLAGS ]]
	then
		TENSORFLOW_BUILD_FLAGS=--copt="$TENSORFLOW_BUILD_FLAGS"
	fi
	bazel build -c opt $CONFIG_CUDA $TENSORFLOW_BUILD_FLAGS //tensorflow/tools/pip_package:build_pip_package >& $logs_dir/build.log &
	build_pid=$!
	echo "   PID: $build_pid"
	echo -n "   Progress: "
	while ps -p $build_pid >& /dev/null
	do
		stat=`tail -1 $logs_dir/build.log | grep -e "\[[0-9,]* / [0-9,]*\]" | sed -e 's!.*\[\([0-9,]*\) / \([0-9,]*\)\] .*!\[\1 / \2\]!g' | sed -e 's!,!!g'`
		if [[ ! -z $stat ]] && [[ $no_terminals_mode -ne 1 ]]
		then
			echo -ne "\r                                     "
			echo -ne "\r   Progress: \033[1;32m$stat\033[0;0m"
		fi
	done
	echo
	wait $build_pid
	if [[ $? -ne 0 ]]; then output_log $logs_dir/build.log; error "Build failed."; fi
	
	rm -f $logs_base_dir/tensorflow_pkg/*
	bazel-bin/tensorflow/tools/pip_package/build_pip_package $logs_base_dir/tensorflow_pkg >> $logs_dir/build.log 2>&1
	if [[ $? -ne 0 ]]; then output_log $logs_dir/build.log; error "Build failed."; fi
	cd - > /dev/null
fi

#################
# COPY SCRIPTS: #
#################
echo "Copying scripts:"
echo "  + Source: $benchmark_dir" 
echo "  + Destination: $work_dir" 

for ip in "${ips[@]}"
do
	get_server_of_ip $ip
	ssh $server mkdir $work_dir
	scp -r $benchmark_dir/* $server:$work_dir > /dev/null &
#	scp -r `find -maxdepth 1 ! -name . ! -name logs` $server:$work_dir > /dev/null &
done
wait

###############
# INSTALL TF: #
###############
if [[ $compile -eq 1 ]]
then
	echo "Installing:"
	for server in $servers
	do
		echo " + $server..."
		ssh $server pip install --user --upgrade $work_dir/tensorflow_pkg/tensorflow-1.* >& $logs_dir/install_$server.log &
	done
	wait
	echo "Done."
fi

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
	scp $server:$work_dir/*.log $logs_dir >& /dev/null
	scp $server:$work_dir/*.json $logs_dir >& /dev/null
done

echo "Done."
echo
[[ $no_terminals_mode -ne 1 ]] && tail -n 15 $logs_dir/worker_0.log
[[ $no_terminals_mode -ne 1 ]] && grep -r " F " $logs_dir/

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
# CLOSE WINDOWS: #
##################
echo "Closing windows..."
pids="`ps -ef | grep $work_dir/run_job.sh | grep -v " grep " | sed -e 's!^[a-zA-Z0-9]* *\([0-9]*\) .*!\1!g'`"

for pid in $pids; do
	echo " + Killing $pid..."
	kill -9 $pid
done

###################
# APPEND RESULTS: #
###################

result=`grep "total images/sec" $logs_dir/worker_0.log | sed -e 's!.*total images/sec: !!g'`
[[ -z $result ]] && error "Run failed. See $logs_dir/ for details."

echo -e "\033[1;32mSuccess.\033[0;0m"

local_results_file="$logs_dir/results.csv"
global_results_file="$logs_base_dir/results.csv"

for file in $local_results_file $global_results_file
do
	if [[ ! -f $file ]]
	then
		printf "%-30s, %-20s, %-12s, %-5s, %-14s, %-11s, %-8s, %-3s, %-10s, %s\n" \
			"Date" "Benchmark" "Model" "Batch" "Protocol" "GPUs/Server" "#Workers" "#PS" "Images/sec" "Comment" >> $file
	fi

	printf "%-30s, %-20s, %-12s, %-5u, %-14s, %-11u, %-8u, %-3u, %-10s, %s\n" \
		"`date`" \
		"$benchmark_name" \
		"$model" \
		$batch_size \
		"$server_protocol" \
		$num_gpus \
		$num_workers \
		$num_ps \
		"$result" \
		"$comment" >> $file
done

echo "See $logs_dir for more info."
