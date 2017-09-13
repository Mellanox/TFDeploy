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

cmd="python -u $script_dir/tf_cnn_benchmarks.py --job_name=$job_name \
                                                --task_index=$task_index \
                                                --ps_hosts=$TF_PS_HOSTS \
                                                --worker_hosts=$TF_WORKER_HOSTS"

for word in $cmd
do
	echo -ne "\033[1;33m$word\033[0;0m "
done
echo

$cmd
set_done 0
