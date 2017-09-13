#!/bin/bash

# afsasfasasffas

RED=$(echo -e "\033[0;31m")
YELLOW=$(echo -e "\033[0;33m")
PURPLE=$(echo -e "\033[0;35m")
NONE=$(echo -e "\033[0m")

function error()
{
	echo -e "\033[1;31mError: $1\033[0;0m"
	exit 1
}

function MarkErrorsAndWarnings()
{
	IFS=''
	while read -r line; do
		echo "$line" | sed -e "s!\(.*[Ee][Rr][Rr][Oo][Rr][ \t]*[:!].*\)!$RED\1$NONE!g" \
								 -e "s!\(.*[Ww][Aa][Rr][Nn][Ii][Nn][Gg][ \t]*[:!].*\)!$YELLOW\1$NONE!g" \
								 -e "s!\(<type 'exceptions.*'>,\)\(.*\)!\1$RED\2$NONE!g" \
								 -e "s!\(.*File \".*\.py\", line [0-9]\+, in .*\)!$NONE\1$NONE!g"
	done
}

function BashExecute()
{
	$1
	res=$?
	if [[ $res -eq 0 ]]; then
		echo -e -n "[\033[0;32mV\033[0;0m] "
	else
		echo -e -n "[\033[0;31mX\033[0;0m] "
	fi
	echo $1
	return $res
}
