#!/usr/bin/python
# -*- coding: utf-8 -*-

import threading
import os
import time
from Actions.Util import executeCommand, waitForProcesses, executeRemoteCommand
import sys
import re

###############################################################################

class Monitor(object):
    
    def __init__(self, server, out, time_interval = 0.1, sample_ratio = 30):
        self._server = server
        self._out = out
        self._output("%s, %s, %s, %s, %s\n" % ("VAL", "TOTAL", "MIN", "MAX", "AVG"))
        self._time_interval = time_interval
        self._sample_ratio = sample_ratio
        self._last = None
    
    # -------------------------------------------------------------------- #
    
    def _output(self, msg):
        if self._out is not None:
            self._out.write(msg)
            self._out.flush()
    
    # -------------------------------------------------------------------- #
    
    def start(self):
        self._stop = False
        self._thread = threading.Thread(target=self.doMonitor)
        self._thread.start()
        
    # -------------------------------------------------------------------- #

    def stop(self):
        if not self.isRunning():
            return
        self._stop = True
        self._thread = None
        
    # -------------------------------------------------------------------- #
    
    def isRunning(self):
        return self._thread is not None
    
    # -------------------------------------------------------------------- #
    
    def doMonitor(self):
        total = 0.0
        count = 0
        max_val = float("-inf")
        min_val = float("inf")
        while not self._stop:
            val = self.monitorAction()
            if val is None:
                return
            total += val
            count += 1
            average = total / count
            max_val = max(val, max_val)
            min_val = min(val, min_val)
            if count % self._sample_ratio == 0:
                self._output("%.2lf, %.2lf, %u, %.2lf, %.2lf, %.2lf\n" % (val, total, count, average, min_val, max_val))
            self._last = (val, total, count, average, min_val, max_val)
            time.sleep(self._time_interval)

        # -------------------------------------------------------------------- #

    def get(self):
        return self._last            
    
    # -------------------------------------------------------------------- #
    
    def monitorAction(self):
        raise Exception("Unimplemented monitorAction")
        return 0.0

###############################################################################

class GPUMontior(Monitor):

    def __init__(self, server, out, time_interval = 0.1, sample_ratio = 30):
        super(GPUMontior, self).__init__(server, out, time_interval, sample_ratio)
    
    # -------------------------------------------------------------------- #
            
    def monitorAction(self):
        results = []
        def _onOut(line, process):
            m = re.search(" [0-9]+% ", line)
            if m is not None:
                results.append(float(m.group(0)[1:-2]))
            
        cmd = "nvidia-smi"
        processes = executeRemoteCommand([self._server], cmd, verbose=False)
        res = waitForProcesses(processes, on_output=_onOut, verbose=False)
        if not res:
            self.stop()
            return None
        return sum(results) / len(results)
    
###############################################################################

class CPUMontior(Monitor):

    def __init__(self, server, pid, out, time_interval = 0.1, sample_ratio = 30):
        super(CPUMontior, self).__init__(server, out, time_interval, sample_ratio)
        self._pid = pid
    
    # -------------------------------------------------------------------- #
            
    def monitorAction(self):
        results = []
        def _onOut(line, process):
            results.append(float(line.split()[8]))
            
        cmd = "top -b -p %u -n 1 | tail -1" % self._pid
        processes = executeRemoteCommand([self._server], cmd, verbose=False)
        res = waitForProcesses(processes, on_output=_onOut, verbose=False)
        if not res:
            self.stop()
            return None
        return results[0]
   
###############################################################################################################################################################
#
#                                                                         APP
#
###############################################################################################################################################################

       
if __name__ == '__main__':
    #prompt.setData([[7,0,1,2],[8,3,4,5]], ["R","F","G","H"], ["S","T"])
#    file_path = "/tmp/test.csv"
    monitor = CPUMontior("12.12.12.25", 1, sys.stdout, sample_ratio=30)
    monitor.start()
    print "Monitor started..."
    try:
        while monitor.isRunning():
            time.sleep(10)
    except KeyboardInterrupt:
        monitor.stop()
    print "Monitor stopped."
#    print "See: %s" % file_path
