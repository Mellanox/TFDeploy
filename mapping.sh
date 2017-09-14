#!/bin/bash

declare -A ip_to_server=( ["192.168.30.2"]="trex-00" \
                          ["192.168.40.2"]="trex-00" \
                          ["192.168.30.1"]="trex-02" \
                          ["192.168.40.1"]="trex-02" )

function get_server_of_ip() # IP
{
	server="${ip_to_server[$1]}"
	if [[ -z $server ]]; then
		server="$1"
	fi
	if [[ $server == "localhost" ]]; then
		server=`hostname`
	fi
}
