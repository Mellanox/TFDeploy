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
echo "   + RDMA device: $RDMA_DEVICE"
echo -e "\033[0;0m"

function set_done()
{
	if [[ ($job_name == worker) && ($task_index -eq 0) ]]; then
		touch done.txt
	fi
	exit $1
}

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda/lib64/
if [[ $job_name == "ps" ]]; then
	export CUDA_VISIBLE_DEVICES=""
fi

cmd="python -u $script_dir/tf_cnn_benchmarks.py --job_name=$job_name \
                                                --task_index=$task_index \
                                                --ps_hosts=$TF_PS_HOSTS \
                                                --worker_hosts=$TF_WORKER_HOSTS"
                                                
if [[ $job_name == "worker" ]]; then
	[[ ! -z $TF_MODEL ]]             && cmd="$cmd --model=$TF_MODEL"
	[[ ! -z $TF_NUM_GPUS ]]          && cmd="$cmd --num_gpus=$TF_NUM_GPUS --local_parameter_device=gpu"
	[[ ! -z $TF_BATCH_SIZE ]]        && cmd="$cmd --batch_size=$TF_BATCH_SIZE"
	[[ ! -z $TF_SERVER_PROTOCOL ]]   && cmd="$cmd --server_protocol=$TF_SERVER_PROTOCOL"
	[[ -d /data/ ]]                  && cmd="$cmd --data_dir=/data/imagenet_data/"
fi

for word in $cmd
do
	echo -ne "\033[1;33m$word\033[0;0m "
done
echo

$cmd
set_done 0
