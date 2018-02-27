#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import threading
import time
import os
import signal
sys.path.insert(0, "..")
from Monitor import Measurement
from Common.Util import executeRemoteCommand, BasicProcess, processCommunicateLive
from Common.Log import log, error



class RemoteMonitor(object):
    
    def __init__(self, server, bin, args, title = None, log_file_path = None, on_new_process = None):
        factory = None if log_file_path is None else BasicProcess.getFactory(title, log_file_path)
        self.monitor_process = executeRemoteCommand([server], "python -u " + bin + " " + args, factory=factory, verbose=False)[0]
        if on_new_process is not None:
            on_new_process(self.monitor_process)
        self.pid = self.monitor_process.instance.pid
        self.pgid = os.getpgid(self.pid)
        log("Running remote monitor process: %u. Group: %u." % (self.pid, self.pgid))
        self.listen_thread = threading.Thread(target=processCommunicateLive, args=(self.monitor_process, self._parseOutput, error))
        self.listen_thread.start()
        self.res = None
    
    # -------------------------------------------------------------------- #
    
    def close(self, on_process_done = None):
        os.killpg(self.pgid, signal.SIGTERM)
        self.listen_thread.join()
        if on_process_done is not None:
            on_process_done(self.monitor_process)
    
    # -------------------------------------------------------------------- #
    
    def _parseOutput(self, line, process):
        if line.startswith(">>>"):
            line = line.replace(">>> ", "")
            self.res = line.split()
        else:
            log(line)
      
    # -------------------------------------------------------------------- #
    
    def _send(self, cmd):
        self.monitor_process.instance.stdin.write(cmd + "\n")
        
    # -------------------------------------------------------------------- #
    
    def start(self):
        self._send("start")

    # -------------------------------------------------------------------- #
    
    def stop(self):
        self._send("stop")

    # -------------------------------------------------------------------- #
    
    def get(self, phrases = ""):
        self.res = None
        self._send("print " + " ".join(phrases))
        while self.res is None:
            time.sleep(0.01)
        return self.res
    
    # -------------------------------------------------------------------- #
    
    def search(self, pattern = ""):
        self.res = None
        self._send("search " + pattern)
        while self.res is None:
            time.sleep(0.01)
        return self.res
    
    # -------------------------------------------------------------------- #
    
    def fillMeasurement(self, measurement):
        res = self.get([measurement.name])
        measurement.count = float(res[1])
        measurement.val   = float(res[2])            
        measurement.total = float(res[3])
        measurement.avg   = float(res[4])
        measurement.min   = float(res[5])
        measurement.max   = float(res[6])
        if measurement.rate is not None:
            measurement.rate.count = float(res[8])
            measurement.rate.val   = float(res[9])            
            measurement.rate.total = float(res[10])
            measurement.rate.avg   = float(res[11])
            measurement.rate.min   = float(res[12])
            measurement.rate.max   = float(res[13])
                
###############################################################################################################################################################
#
#                                                                         APP
#
###############################################################################################################################################################
       
if __name__ == '__main__':
    
    rm = RemoteMonitor("12.12.12.25", "/home/eladw/TFDeploy/GUI/Monitor.py", "--cpu 1,2 0 --gpu 0 --net mlx5_0:1 0.1 -d .")
    print rm.search()
    print rm.search("GPU")
    print rm.get()
    print rm.get(["STIME-1"])
    print rm.get(["STIME-1.val"])
    print rm.get(["STIME-1.avg", "RDTA-mlx5_0:1.avg", "TDTA-mlx5_0:1.rate.avg"])
    
    cpu = Measurement("STIME-2", "%")
    rm.fillMeasurement(cpu)
    print cpu

    rm.close()
#     while line != "":
#         print line
#         line = process.instance.stdout.readline()    
#     
#     waitForProcesses([process])
    