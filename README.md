# TFDeploy
TensorFlow deploy script to easily run on multiple servers

Please send feedbacks and requests to eladw@mellanox.com

## Description:
Based on given parameters, the script will automatically generate and execute the relevant commands to run tensorflow benchmark on each  of the desired run-servers.

The benchmark scripts are copied per run-server.

If specified, the script will compile tensorflow on the source-station (the station where .deploy is invoked) and install the result .whl on each of the run servers (only for the current user). This is conveniently allows the user to store and modify the tensorflow code only on the source-station. A downside of this is that the source-station should have similiar (relevant) drivers as the run servers.

When compiling, TENSORFLOW_HOME 

## Prerequisites
* tensorflow 
* tf_cnn_benchmarks
* gnome-terminal installed (the script will open a new terminal for each ps/worker being run)
* It is recommended to do ssh-copy-id once for each of the desired run-servers, in order to avoid having to enter a password each time.
* When running with compile (-c), the environment variable TENSORFLOW_HOME should point to the tensorflow repository home folder. Default is "/root/tensorflow"


## Usage:
```
ln -s TFDeploy/*.sh tf_cnn_benchmarks
cd tf_cnn_benchmarks
./deploy.sh
```
