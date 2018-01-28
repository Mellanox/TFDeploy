#!/usr/bin/python
# -*- coding: utf-8 -*-

import threading
from tensorflow.python.framework.errors_impl import UnimplementedError
import os
import time
from Actions.Util import executeCommand, waitForProcesses
import sys
import re

###############################################################################

class Monitor(object):
    
    def __init__(self, 
                 out, 
                 time_interval = 0.1, 
                 sample_ratio = 30 # In order to not explode the file, write to file every N samples
                 ):
        self._out = out
        self._out.write("%s, %s, %s, %s, %s\n" % ("VAL", "TOTAL", "MIN", "MAX", "AVG"))
        self._time_interval = time_interval
        self._sample_ratio = sample_ratio
    
    # -------------------------------------------------------------------- #
    
    def Start(self):
        self._stop = False
        self._thread = threading.Thread(target=self.DoMonitor)
        self._thread.start()
        
    # -------------------------------------------------------------------- #

    def Stop(self):
        if not self.isRunning():
            return
        
        self._stop = True
        self._thread = None
        self._out.close()
        
    # -------------------------------------------------------------------- #
    
    def isRunning(self):
        return self._thread is not None
    
    # -------------------------------------------------------------------- #
    
    def DoMonitor(self):
        total = 0.0
        count = 0
        max_val = float("-inf")
        min_val = float("inf")
        while not self._stop:
            val = self.MonitorAction()
            if val is None:
                return
            total += val
            count += 1
            average = total / count
            max_val = max(val, max_val)
            min_val = min(val, min_val)
            if count % self._sample_ratio == 0:
                self._out.write("%.2lf, %.2lf, %.2lf, %.2lf, %.2lf\n" % (val, total, min_val, max_val, average))
                self._out.flush()
            time.sleep(self._time_interval)
            
    # -------------------------------------------------------------------- #
    
    def MonitorAction(self):
        raise UnimplementedError("Unimplemented MonitorAction")
        return 0.0

###############################################################################

class GPUMontior(Monitor):

    def __init__(self, out, time_interval = 0.1, sample_ratio = 30):
        super(GPUMontior, self).__init__(out, time_interval, sample_ratio)
    
    # -------------------------------------------------------------------- #
            
    def MonitorAction(self):
        results = []
        def _onOut(line, process):
            m = re.search(" [0-9]+% ", line)
            if m is not None:
                results.append(float(m.group(0)[1:-2]))
            
        cmd = "nvidia-smi"
        process = executeCommand(cmd, verbose=False)
        res = waitForProcesses([process], on_output=_onOut, verbose=False)
        if not res:
            self.Stop()
            return None
        
        print results
        return sum(results) / len(results)
    
###############################################################################

class CPUMontior(Monitor):

    def __init__(self, out, time_interval = 0.1, sample_ratio = 30):
        super(GPUMontior, self).__init__(out, time_interval, sample_ratio)
    
    # -------------------------------------------------------------------- #
            
    def MonitorAction(self):
        results = []
        def _onOut(line, process):
            m = re.search(" [0-9]+% ", line)
            if m is not None:
                results.append(float(m.group(0)[1:-2]))
            
        cmd = "top -b -p $child_pid"
        process = executeCommand(cmd, verbose=False)
        res = waitForProcesses([process], on_output=_onOut, verbose=False)
        if not res:
            self.Stop()
            return None
        
        print results
        return sum(results) / len(results)    
 
###############################################################################################################################################################
#
#                                                                         APP
#
###############################################################################################################################################################

       
if __name__ == '__main__':
    #prompt.setData([[7,0,1,2],[8,3,4,5]], ["R","F","G","H"], ["S","T"])
#    file_path = "/tmp/test.csv"
    monitor = GPUMontior(sys.stdout, sample_ratio=30)
    monitor.Start()
    print "Monitor started..."
    try:
        while monitor.isRunning():
            time.sleep(10)
    except KeyboardInterrupt:
        monitor.Stop()
    print "Monitor stopped."
#    print "See: %s" % file_path
    



