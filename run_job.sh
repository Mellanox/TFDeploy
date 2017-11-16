#!/bin/bash

script_dir=`dirname $0`
cd $script_dir

job_name=$1
task_index=$2

title="[$(dirname $0)]: `hostname`  - $job_name:$task_index"
echo -ne "\033]0;$title\007"

echo -e "\033[1;32m"
echo "Running `hostname`:"
echo "   + Job Name: $job_name" 
echo "   + Task Index: $task_index"
echo "   + PS hosts: $TF_PS_HOSTS"
echo "   + Worker hosts: $TF_WORKER_HOSTS"
echo "   + Model: $TF_MODEL"

function set_done()
{
	if [[ ($job_name == worker) && ($task_index -eq 0) ]]; then
		touch done.txt
	fi
	exit $1
}

####################
# Get device name: #
####################
PATH="$PATH:/usr/sbin"
DEVICE_NAME=`ip -o a s | grep $DEVICE_IP | cut -d ' ' -f 2 | cut -d'.' -f1`
if [[ ! -z $DEVICE_NAME ]]
then
	echo "Using IP device: $DEVICE_NAME ($DEVICE_IP)"
	ibdev_line=`ibdev2netdev | grep $DEVICE_NAME 2>/dev/null`
	if [[ ! -z $ibdev_line ]]
	then
		export RDMA_DEVICE=`echo $ibdev_line | cut -d' ' -f1`
		export RDMA_DEVICE_PORT=`echo $ibdev_line | cut -d' ' -f3`
		export RDMA_GID_INDEX=3
		export RDMA_PKEY=0
		export RDMA_QUEUE_DEPTH=1024
		export RDMA_TIMEOUT=10
		export RDMA_RETRY_CNT=10
		export RDMA_SL=1
		export RDMA_MTU=512
		export RDMA_TRAFFIC_CLASS=8
		echo "   + RDMA device: $RDMA_DEVICE"
		echo "   + RDMA port: $RDMA_DEVICE_PORT"
		echo "   + RDMA GID INDEX: $RDMA_GID_INDEX"
		echo "   + RDMA pkey_index: $RDMA_PKEY"
		echo "   + RDMA queue depth: $RDMA_QUEUE_DEPTH"
		echo "   + RDMA timeout: $RDMA_TIMEOUT"
		echo "   + RDMA retry_cnt: $RDMA_RETRY_CNT"
		echo "   + RDMA sl: $RDMA_SL"
		echo "   + RDMA mtu: $RDMA_MTU"
	    echo "   + RDMA traffic class: $RDMA_TRAFFIC_CLASS"
		if [[ -z `echo $ibdev_line | grep Up` ]]
		then
			echo -e "\033[1;31mDevice is down.\033[0;0m"
			set_done 1
		fi
	else
		echo " + Not an RDMA device."
	fi
fi
echo -e "\033[0;0m"

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda/lib64/
if [[ $job_name == "ps" ]]
then
	export CUDA_VISIBLE_DEVICES=""
fi

[[ $TF_CPP_MIN_VLOG_LEVEL == "x" ]] && GDB_OPTION="gdb --args"
cmd="$GDB_OPTION python -u $script_dir/tf_cnn_benchmarks.py"

if [[ ! -z $TF_PS_HOSTS ]]
then
 	cmd="$cmd --job_name=$job_name"
	cmd="$cmd --task_index=$task_index"
	cmd="$cmd --ps_hosts=$TF_PS_HOSTS"
	cmd="$cmd --worker_hosts=$TF_WORKER_HOSTS"
fi

[[ ! -z $TF_SERVER_PROTOCOL ]]   && cmd="$cmd --server_protocol=$TF_SERVER_PROTOCOL"

if [[ $job_name == "worker" ]]
then
	[[ ! -z $TF_MODEL ]]             && cmd="$cmd --model=$TF_MODEL"
	[[ ! -z $TF_NUM_GPUS ]]          && cmd="$cmd --num_gpus=$TF_NUM_GPUS --local_parameter_device=gpu"
	[[ ! -z $TF_BATCH_SIZE ]]        && cmd="$cmd --batch_size=$TF_BATCH_SIZE"
	[[ ! -z $TF_DATA_DIR ]]          && cmd="$cmd --data_dir=$TF_DATA_DIR"
fi

for word in $cmd
do
	echo -ne "\033[1;33m$word\033[0;0m "
done
echo

if [[ ! -z $GDB_OPTION ]]
then
	$cmd
	set_done 0
	exit
fi

output_fifo="${job_name}_${task_index}_fifo"
mkfifo $output_fifo
$cmd >& $output_fifo &
child_pid=$!
echo $child_pid
while true; do
    if jobs %% >&/dev/null; then
        if read -r -u 9 line; then
		if [[ "$line" =~ "images/sec" ]]; then
			process_stats=`ps -p $child_pid -o %cpu,%mem | tail -1`
			cpu_usage=`echo $process_stats | cut -d' ' -f1`
			mem_usage=`echo $process_stats | cut -d' ' -f2`
			gpus_usage=`nvidia-smi | grep -e " [0-9]\+% " | sed -e 's!.* \([0-9]\+%\) .*!\1!g'`
			
			echo -ne "[CPU: $cpu_usage% MEM: $mem_usage%"
			gpu_id=0
			for gpu_usage in $gpus_usage 
			do
				[[ $gpu_usage != "0%" ]] && echo -ne " GPU-$gpu_id: $gpu_usage"
				gpu_id=$((gpu_id+1))
			done
			echo "] $line"
		else
			echo "$line"
		fi
        fi
    else
        break
    fi
done 9< "${output_fifo}"

set_done 0
