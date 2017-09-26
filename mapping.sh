#!/bin/bash

declare -A ip_to_server=( ["99.99.99.0"]="server-0" \
                          ["99.99.99.1"]="server-1" \
                          ["99.99.99.2"]="server-2" )

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
