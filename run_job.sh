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

echo -ne "\033[1;33m$cmd\033[0;0m\n"

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
output_fifo="fifo_${job_name}_${task_index}"
mkfifo $output_fifo
$cmd >& $output_fifo &
child_pid=$!
while read -r -u 9 line
do
	if [[ ! "$line" =~ images/sec ]]
	then
		echo $line
		continue
	fi

	if [[ "$line" =~ total\ images/sec ]]
	then
		step="###"
		loss=""
		images_sec="$line"
		cpu_usage=`python -c "print $total_cpu_usage / 10.0"`
		rmbps=`python -c "print '%u' % ($total_rmbps / 11.0)"`
		tmbps=`python -c "print '%u' % ($total_tmbps / 11.0)"`
		gpu_usage=`python -c "print '%u' % ($total_gpu_usage / 22.0)"`
		for dummy in $gpus_usage 
		do
			new_gpus_usage="$new_gpus_usage $gpu_usage"
		done
		gpus_usage=$new_gpus_usage
	else
		process_stats=`top -b -p $child_pid -n 1 | grep $tf_cnn_benchmarks.py`
		cpu_usage=`echo $process_stats | cut -d' ' -f9`; [[ -z $cpu_usage ]] && cpu_usage=0
		mem_usage=`echo $process_stats | cut -d' ' -f10`; [[ -z $mem_usage ]] && mem_usage=0
		[[ $TF_NUM_GPUS -gt 0 ]] && gpus_usage=`nvidia-smi | grep -e " [0-9]\+% " | sed -e 's!.* \([0-9]\+\)% .*!\1!g'`
		total_cpu_usage=`python -c "print $total_cpu_usage + $cpu_usage"`
	
		rpkt=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_rcv_packets`
		rdta=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_rcv_data`
		rpktd=$((rpkt - rpktold))
		rdtad=$((rdta - rdtaold))
		rmbps=$((rdtad * 4 * 8 / 1000 / 1000))
		total_rmbps=`python -c "print $total_rmbps + $rmbps"`
	
		tpkt=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_xmit_packets`
		tdta=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_xmit_data`
		tpktd=$((tpkt - tpktold))
		tdtad=$((tdta - tdtaold))
		tmbps=$((tdtad * 4 * 8 / 1000 / 1000))
		total_tmbps=`python -c "print $total_tmbps + $tmbps"`
	
		rpktold=$rpkt; rdtaold=$rdta;
		tpktold=$tpkt; tdtaold=$tdta;
		
		################
		# Print header #
		################
		if [[ -z $step ]]
		then
			printf "%-6s, %-3s, %-12s, " "CPU" "MEM" "RX/TX (Mbit)"
			[[ $TF_NUM_GPUS -gt 0 ]] && gpus_usage=`nvidia-smi | grep -e " [0-9]\+% " | sed -e 's!.* \([0-9]\+\)% .*!\1!g'`
			gpu_id=0
			for gpu_usage in $gpus_usage
			do
				printf "%-6s, " "GPU-$gpu_id"
				gpu_id=$((gpu_id+1))
			done
			printf "%-4s, %-50s, %-5s\n" "Step" "Img/sec" "loss"
		fi

		step=`echo $line | cut -d' ' -f1`
		loss=`echo $line | sed -e 's!.*images/sec.*) *\([0-9\.]*\)!\1!g'`
		images_sec=`echo $line | sed -e 's!.*\(images/sec.*)\) .*!\1!g'`
	fi

	##############
	# Print line #
	##############
	printf "%-6.1f, %-3s, %-12s, " "$cpu_usage" "$mem_usage" "$rmbps/$tmbps"
	for gpu_usage in $gpus_usage 
	do
		printf "%-6s, " "$gpu_usage%"
		total_gpu_usage=`python -c "print $total_gpu_usage + $gpu_usage"`
	done
	printf "%-4s, %-50s, %-5s\n" "$step" "$images_sec" "$loss"

	if [[ $loss == nan ]]
	then
		rm $output_fifo
		set_done 1
	fi
done 9< "${output_fifo}"
rm $output_fifo

set_done 0
