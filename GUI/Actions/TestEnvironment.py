#!/usr/bin/python
# -*- coding: utf-8 -*-
import os

###############################################################################

def _onNewProcess(process):
    process.openLog()
    
#--------------------------------------------------------------------#

def _onProcessDone(process):    
    process.closeLog()
    if process.exception is not None:
        raise process.exception    
    return process.instance.returncode in [0, 143, -15]    

###############################################################################

class TestEnvironment(object):
    # On Python 2 if we save without [] we'll get a unbound method
    _on_new_process = [_onNewProcess]
    _on_process_done = [_onProcessDone]
    _instance = None

    @staticmethod
    def Get():
        if TestEnvironment._instance is None:
            TestEnvironment._instance = TestEnvironment()
        return TestEnvironment._instance
    
    # -------------------------------------------------------------------- #
    
    def __init__(self):
        self._test_logs_dir = None
        self._servers_by_ip = { "192.168.1.41": "clx-mld-41",
                                "192.168.1.42": "clx-mld-42",
                                "192.168.1.43": "clx-mld-43",
                                "192.168.1.44": "clx-mld-44",
                                "192.168.1.45": "clx-mld-45",
                                "192.168.1.46": "clx-mld-46",
                                "192.168.1.47": "clx-mld-47",
                                "192.168.1.48": "clx-mld-48",
                                "31.31.31.41": "10.143.119.41",
                                "31.31.31.42": "10.143.119.42",
                                "31.31.31.43": "10.143.119.43",
                                "31.31.31.44": "10.143.119.44",
                                "31.31.31.45": "10.143.119.45",
                                "31.31.31.46": "10.143.119.46",
                                "31.31.31.47": "10.143.119.47",
                                "31.31.31.48": "10.143.119.48",
                                "12.12.12.41": "10.143.119.41",
                                "12.12.12.42": "10.143.119.42",
                                "12.12.12.43": "10.143.119.43",
                                "12.12.12.44": "10.143.119.44",
                                "12.12.12.45": "10.143.119.45",
                                "12.12.12.46": "10.143.119.46",
                                "12.12.12.47": "10.143.119.47",
                                "12.12.12.48": "10.143.119.48" }                                
    
    # -------------------------------------------------------------------- #
        
    def setTestLogsDir(self, val):
        self._test_logs_dir = val
        if not os.path.exists(val):
            os.makedirs(val)
            link = os.path.join(os.path.dirname(val), "last")
            if os.path.islink(link):
                os.remove(link)
                os.symlink(os.path.basename(val), link)

    # -------------------------------------------------------------------- #
    
    def testLogsDir(self):
        return self._test_logs_dir

    # -------------------------------------------------------------------- #
    
    def getServer(self, ip):
        if ip in self._servers_by_ip:
            return self._servers_by_ip[ip]
        return ip

    # -------------------------------------------------------------------- #
    
    def getServers(self, ips):
        return [self.getServer(ip) for ip in ips]
    
    # -------------------------------------------------------------------- # 
    
    @staticmethod
    def onNewProcess():
        return TestEnvironment._on_new_process[0]
        
    @staticmethod
    def onProcessDone():
        return TestEnvironment._on_process_done[0]

    @staticmethod
    def setOnNewProcess(val):
        TestEnvironment._on_new_process[0] = val        
        
    @staticmethod
    def setOnProcessDone(val):
        TestEnvironment._on_process_done[0] = val
        
    @staticmethod
    def setServersByIP(val):
        TestEnvironment._servers_by_ip = val
