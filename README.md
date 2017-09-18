# TFDeploy
TensorFlow deploy script to easily run on multiple servers

## Prerequisites
* tensorflow 
* tf_cnn_benchmarks
* gnome-terminal installed (the script will open a new terminal for each ps/worker being run)

## Usage:
```
ln -s TFDeploy/*.sh tf_cnn_benchmarks
cd tf_cnn_benchmarks
./deploy.sh
```
