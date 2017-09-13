#!/bin/bash

script_dir=`dirname $0`
cd $script_dir

job_name=$1
task_index=$2
ps_hosts=$3
worker_hosts=$4

title="[$(dirname $0)]: `hostname`  - $job_name:$task_index"
echo -ne "\033]0;$title\007"

echo -e "\033[1;32m"
echo "Running `hostname`:"
echo "   + Job Name: $job_name" 
echo "   + Task Index: $task_index"
echo "   + PS hosts: $ps_hosts"
echo "   + Worker hosts: $worker_hosts"
echo
echo -e "\033[0;0m"

function set_done()
{
	if [[ ($job_name == worker) && ($task_index -eq 0) ]]; then
		touch done.txt
	fi
	exit $1
}

function error()
{
	echo -e "\033[1;31mError: $1\033[0;0m"
}

run_env="${job_name}_${task_index}_env"
virtualenv $run_env
if [[ $? -ne 0 ]]; then error "virtualenv not installed. Please install it."; set_done 1; fi

source $run_env/bin/activate
sudo pip install --upgrade $script_dir/tensorflow_pkg/tensorflow-1.3.0*

RDMA_DEVICE=$5 python -u $script_dir/tf_cnn_benchmarks.py --job_name=$job_name \
                                           --task_index=$task_index \
                                           --ps_hosts=$ps_hosts \
                                           --worker_hosts=$worker_hosts
deactivate
rm -rf run_env
set_done 0
