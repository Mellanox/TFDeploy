#!/bin/bash

COLOR_WHITE="\033[07;1m"
COLOR_RED="\033[0;41m"
COLOR_GREEN="\033[0;42m"
COLOR_YELLOW="\033[0;43m"
COLOR_BLUE="\033[0;44m"
COLOR_NONE="\033[0;0m"
server1=$1
server2=$2
silent=$3

[[ -z $TENSORFLOW_HOME ]] && TENSORFLOW_HOME=/root/tensorflow/

function f_nv_peer_mem()
{
	state=$1
	ssh $server1 sudo /etc/init.d/nv_peer_mem $state; res=$?; [[ $res -eq 0 ]] || exit $res
	ssh $server2 sudo /etc/init.d/nv_peer_mem $state; res=$?; [[ $res -eq 0 ]] || exit $res
}

function print_title()
{
	message=$1
	color=$2
	bars=$3
	bar=`printf "=%.0s" {1..120}`
	[[ $bars -eq 1 ]] && printf "$color$bar$COLOR_NONE\n" | tee -a regressions.log
	printf "$color%-120s$COLOR_NONE\n" "$message" | tee -a regressions.log
	[[ $bars -eq 1 ]] && printf "$color$bar$COLOR_NONE\n" | tee -a regressions.log
}

function f_run_test()
{
	flags=$@
	cmd="./deploy.sh"
	[[ $silent -ge 1 ]] && cmd="$cmd -s"
	cmd="$cmd $flags 5000 2 2 $server1 $server2"
	[[ $silent -ge 2 ]] && cmd="$cmd >>& regressions.log"
	print_title "$cmd" $COLOR_WHITE 0
	eval $cmd
	res=$?
	if [[ $res -ne 0 ]]	
	then
		echo "Test failed."
		exit $res
	fi
	sleep 1
}

echo "Server1: $server1"
echo "Server2: $server2"

#-------
# Basic
#-------
print_title "Basic tests" $COLOR_BLUE 1
f_nv_peer_mem start
f_run_test -c -b 32 -n 2 -r /data/imagenet_data/ -m trivial   
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m trivial   
f_run_test -g -b 32 -n 2 -r /data/imagenet_data/ -m trivial   
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m resnet50  
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m resnet152 
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m inception3
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m vgg16     

#------------------------------
# Nvidia-peer-memory disabled:
#------------------------------
print_title "Nvidia peer memory disabled" $COLOR_BLUE 1
f_nv_peer_mem stop
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m trivial   
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m resnet50  
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m resnet152 
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m inception3
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m vgg16     
f_nv_peer_mem start

#------------------
# Data validation: 
#------------------
print_title "Data validation:" $COLOR_BLUE 1

sed -i '1i#define RDMA_DATA_VALIDATION' $TENSORFLOW_HOME/tensorflow/contrib/verbs/verbs_util.h

f_run_test -vc -b 32 -n 2 -r /data/imagenet_data/ -m trivial   
f_run_test -v  -b 32 -n 2 -r /data/imagenet_data/ -m resnet50  
f_run_test -v  -b 32 -n 2 -r /data/imagenet_data/ -m resnet152 
f_run_test -v  -b 32 -n 2 -r /data/imagenet_data/ -m inception3
f_run_test -v  -b 32 -n 2 -r /data/imagenet_data/ -m vgg16     
f_nv_peer_mem stop
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m trivial   
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m resnet50  
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m resnet152 
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m inception3
f_run_test -v -b 32 -n 2 -r /data/imagenet_data/ -m vgg16     
f_nv_peer_mem start

sed -i '1d' $TENSORFLOW_HOME/tensorflow/contrib/verbs/verbs_util.h
