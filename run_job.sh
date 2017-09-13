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

run_env="${job_name}_${task_index}_env"

virtualenv $run_env
source $run_env/bin/activate
pip install --upgrade $script_dir/tensorflow_pkg/tensorflow-1.3.0*

mkdir -p run_logs
python -u $script_dir/tf_cnn_benchmarks.py --job_name=$job_name \
                                           --task_index=$task_index \
                                           --ps_hosts=$ps_hosts \
                                           --worker_hosts=$worker_hosts 2>&1 | tee $script_dir/run_logs/${job_name}_${task_index}.log
deactivate
rm -rf run_env

if [[ ($job_name == worker) && ($task_index -eq 0) ]]; then
	touch done.txt
fi

