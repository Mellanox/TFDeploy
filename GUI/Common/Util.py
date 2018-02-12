#!/usr/bin/python
# -*- coding: utf-8 -*-

import subprocess
import time
import threading
import sys
from Log import log,error,title,UniBorder,LOG_LEVEL_NOTE
import os

###############################################################################

class BasicProcess(object):
        
    @classmethod
    def getFactory(cls, title, log_file_path):
        def op(instance, server):
            return cls(instance, title, log_file_path, server)
        return op 
    
    # -------------------------------------------------------------------- #
    
    def _getStrValue(self, value):
        if value is None:
            return None
        if isinstance(value, basestring):
            return value
        return value(self)
        
    # -------------------------------------------------------------------- #
    
    def __init__(self, instance, title, log_file_path, server):
        self.instance = instance
        self.server = server
        self.title = self._getStrValue(title)
        self.log_file_path = self._getStrValue(log_file_path)        
        self._log_file = None
                
        # Note: Vulnerable to race conditions:
        #if log_file_path is not None:
        #    i = 1
        #    while os.path.exists(log_file_path):
        #        base, ext = os.path.splitext(log_file_path)
        #        log_file_path = "%s_%u%s" % (base, i, ext)
        # self.log_file_path = log_file_path

        
    # -------------------------------------------------------------------- #
            
    def openLog(self):
        if self.log_file_path is None:
            return
        prefix = "" if self.instance is None else "Process %u: " % self.instance.pid
        log("%sSee log %s" % (prefix, self.log_file_path), log_level = LOG_LEVEL_NOTE)
        self._log_file = open(self.log_file_path, "w") 

    # -------------------------------------------------------------------- #
    
    def closeLog(self):
        if self._log_file is not None:
            self._log_file.close()
            
    # -------------------------------------------------------------------- #
    
    def log(self, line, log_level):
        if self._log_file is not None:
            self._log_file.write(line + "\n")
            self._log_file.flush()


###############################################################################        

def processCommunicateLive(process, on_output = None, on_error = None):
    while True:
        out = process.instance.stdout.readline()
        #err = process.stderr.readline()
        err = ""
        if (out == "") and (err == "") and (process.instance.poll() is not None):
            break
        if (out != "") and (on_output is not None):
            on_output(out[:-1], process)
        if (err != "") and (on_error is not None):
            on_error(err[:-1], process)
        
# -------------------------------------------------------------------- #

def checkRetCode(process):
    return process.instance.returncode == 0

# -------------------------------------------------------------------- #

def waitForProcesses(processes, 
                     wait_timeout = sys.maxint,
                     on_output = log, 
                     on_error = error,
                     on_process_start = None,
                     on_process_done = checkRetCode,
                     verbose = True):
    '''
    Wait for a group of processes to finish, but run them in parallel.
    '''
    if verbose:
        log("Waiting for processes: %s" % [process.instance.pid for process in processes])    
    threads = []
    for process in processes:
        thread = threading.Thread(target=processCommunicateLive, args=(process,on_output,on_error))
        threads.append(thread)
        thread.start()
        if on_process_start is not None:
            on_process_start(process)

    all_ok = True
    elapsed = 0
    while elapsed < wait_timeout:
        num_remaining_processes = len(processes)
        i = 0
        while i < num_remaining_processes:
            process = processes[i]
            thread = threads[i]
            if not thread.is_alive():
                retcode = process.instance.returncode
                pid = process.instance.pid
                if retcode != 0:
                    error("Process %u exited with error code %d (elapsed: %.2lf)" % (pid, (0xdeadbeef if retcode is None else retcode), elapsed))
                else:
                    if verbose:
                        log("Process %u finished successfully (elapsed: %.2lf)" % (pid, elapsed))
                is_ok = on_process_done(process)
                all_ok = all_ok and is_ok
                processes.pop(i)
                threads.pop(i)
                num_remaining_processes -= 1
            else:
                i += 1
        if len(processes) == 0:
            break
        elapsed += 0.1
        time.sleep(0.1)
            
    # All remaining threads got timeout:            
    for process in processes:
        error("Process %u got timeout (%.2lf)." % (process.instance.pid, wait_timeout))
        is_ok = on_process_done(process)
        all_ok = all_ok and is_ok
    return all_ok

# -------------------------------------------------------------------- #

def executeCommand(command, factory = None, server = None, verbose = True):
    if factory is None:
        factory = BasicProcess.getFactory(None, None)
    if verbose:
        log("Running command: %s" % command)
    instance = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
    return factory(instance, server)

# -------------------------------------------------------------------- #

def executeRemoteCommand(servers, command, user = None, factory = None, verbose = True):
    processes = []
    for server in servers:
        remote = server if user is None else "%s@%s" % (user, server)
        cmd = "ssh %s -C \"%s\"" % (remote, command)
        process = executeCommand(cmd, factory = factory, server = server, verbose = verbose)
        processes.append(process)
    return processes

# -------------------------------------------------------------------- #

def copyToRemote(servers, sources, remote_dir, user = None, factory = None, verbose = True):
    processes = []    
    for server in servers:
        remote = server if user is None else "%s@%s" % (user, server)
        cmd = "scp -r " + " ".join(sources) + " %s:%s" % (remote, remote_dir)
        process = executeCommand(cmd, factory = factory, server = server, verbose = verbose)
        processes.append(process)
    return processes

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
#     title("Running some processes:")
    processes = []
    processes.append(executeCommand("echo A"))
    processes.append(executeCommand("echo B"))
    processes.append(executeCommand("echo C"))
    processes.append(executeCommand("a_bad_command"))
    processes.append(executeCommand("ls /x/x/x/x/x/"))
    processes.append(executeCommand("echo D"))    
    processes.append(executeCommand("sleep 2"))
    processes.append(executeCommand("echo E"))    
    processes.append(executeCommand("sleep 999"))
    processes.append(executeCommand("echo F"))
    processes.append(executeCommand("bash -c 'for i in {1..5}; do echo $i; sleep 1; done'"))
    processes.extend(executeRemoteCommand(["12.12.12.26"], "python -u /tmp/tmp.A453n4kxCRS2/Monitor.py --cpu 35460 0 --gpu 0 --net mlx5_1 1 0.1 -d /tmp/test_logs/step_0_TF_CNN_Benchmarks__trivial__grpc_verbs__2_GPUs__batch_32/graphs/worker_0"))

    title("Waiting for processes:", style=UniBorder.BORDER_STYLE_DOUBLE)
    waitForProcesses(processes, wait_timeout=5, on_output=log, on_error=error)
    