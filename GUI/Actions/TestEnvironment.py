#!/usr/bin/python
# -*- coding: utf-8 -*-
from GPUMonitor import GPUMontior, CPUMontior

###############################################################################

class TestEnvironment(object):
    # On Python 2 if we save without [] we'll get a unbound method
    _on_out = [None]
    _on_err = [None]
    _on_new_process = [None]
    _on_process_done = [None]
    _logs_folder = [None]
    _gpu_monitors = {}
    _cpu_monitors = {}    
    
    @staticmethod
    def onOut():
        return TestEnvironment._on_out[0]
            
    @staticmethod
    def onErr():
        return TestEnvironment._on_err[0]
    
    @staticmethod
    def onNewProcess():
        return TestEnvironment._on_new_process[0]
        
    @staticmethod
    def onProcessDone():
        return TestEnvironment._on_process_done[0]

    @staticmethod
    def logsFolder():
        return TestEnvironment._logs_folder[0] 
                
    @staticmethod
    def setOnOut(val):
        TestEnvironment._on_out[0] = val

    @staticmethod
    def setOnErr(val):
        TestEnvironment._on_err[0] = val

    @staticmethod
    def setOnNewProcess(val):
        TestEnvironment._on_new_process[0] = val        
        
    @staticmethod
    def setOnProcessDone(val):
        TestEnvironment._on_process_done[0] = val
        
    @staticmethod
    def setLogsFolder(val):
        TestEnvironment._logs_folder[0] = val
        
    @staticmethod
    def getGPUMonitor(server):
        if server in TestEnvironment._gpu_monitors:
            return TestEnvironment._gpu_monitors[server]
        monitor = GPUMontior(server, None, 0, 1)
        TestEnvironment._gpu_monitors[server] = monitor
        return monitor
    
    @staticmethod
    def getCPUMonitor(server, pid):
        key = (server, pid)
        if key in TestEnvironment._cpu_monitors:
            return TestEnvironment._cpu_monitors[key]
        monitor = CPUMontior(server, pid, None, 0, 1)
        TestEnvironment._cpu_monitors[key] = monitor
        return monitor    
        