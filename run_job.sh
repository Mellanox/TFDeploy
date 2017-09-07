#!/bin/bash

script_dir=`dirname $0`
cd $script_dir

job_name=$1
task_id=$2
ps_hosts=$3
worker_hosts=$4


title="[$(dirname $0)]: `hostname`  - $job_name:$task_id"
echo -ne "\033]0;$title\007"

echo -e "\033[1;32m"
echo "Running `hostname`:"
echo "   + Job: $job_name" 
echo "   + Task ID: $task_id"
echo "   + PS hosts: $ps_hosts"
echo "   + Worker hosts: $worker_hosts"
echo
echo -e "\033[0;0m"

mkdir -p run_logs
python -u $script_dir/tf_cnn_benchmarks.py $job_name $task_id $ps_hosts $worker_hosts 2>&1 | tee $script_dir/run_logs/${job_name}_${task_id}.log

if [[ ($job_name == worker) && ($task_id -eq 0) ]]; then
	touch done.txt
fi

