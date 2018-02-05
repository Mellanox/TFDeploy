#!/bin/bash

script_dir=`dirname $0`
cd $script_dir

job_name=$1
task_index=$2

title="[$(dirname $0)]: `hostname`  - $job_name:$task_index"
#echo -ne "\033]0;$title\007"

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

################  UCX  ######################
                export UCX_NET_DEVICES=$RDMA_DEVICE:$RDMA_DEVICE_PORT 
# Ucx should be compiled ./contrib/configure-devel --enable-debug 
		#export UCX_IB_ETH_PAUSE_ON=y
		#export UCX_LOG_LEVEL=trace 

################  GRPC debugging ############
		#export GRPC_VERBOSITY=DEBUG
		#export GRPC_TRACE=api,call_combiner
		#export GRPC_TRACE=queue_pluck,flowctl,http1,http2_stream_state,http,op_failure
		#export GRPC_TRACE=client_channel,call_error,channel,server_channel,channel_stack_builder,connectivity_state  #all
                echo "   + UCX device: $UCX_NET_DEVICES"
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
			echo -e "Device is down."
			set_done 1
		fi
	else
		echo " + Not an RDMA device."
	fi
fi

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda/lib64/
if [[ $job_name == "ps" ]]
then
	export CUDA_VISIBLE_DEVICES=""
fi

[[ $TF_CPP_MIN_VLOG_LEVEL == "x" ]] && GDB_OPTION="gdb --args"
[[ $TF_CPP_MIN_VLOG_LEVEL == "p" ]] && TF_ADDITIONAL_FLAGS="$TF_ADDITIONAL_FLAGS --trace_file=trace_${job_name}_${task_index}.json"
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
	[[ ! -z $TF_BATCH_SIZE ]]        && cmd="$cmd --batch_size=$TF_BATCH_SIZE"
	[[ ! -z $TF_DATA_DIR ]]          && cmd="$cmd --data_dir=$TF_DATA_DIR"
	[[ $TF_NUM_GPUS -gt 0 ]]         && cmd="$cmd --num_gpus=$TF_NUM_GPUS --local_parameter_device=gpu"
fi

cmd="$cmd $TF_ADDITIONAL_FLAGS"

echo -ne "$cmd\n"

if [[ ! -z $GDB_OPTION ]]
then
	$cmd
	set_done 0
fi
			
rpktold=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_rcv_packets`
rdtaold=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_rcv_data`
tpktold=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_xmit_packets`
tdtaold=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_xmit_data`
total_gpu_usage=0
total_cpu_usage=0
total_rmbps=0
total_tmbps=0

################################
# Run command and format stats #
################################
$cmd &
child_pid=$!
echo "PROCESS ID: $child_pid"
wait $child_pid
res=$?
set_done $res

