#!/usr/bin/python
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import threading

# -------------------------------------------------------------------- #

def log_write(msg, process, stream):
    pid = "" if process is None else " %u" % process.pid
    stream.write("[%s%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), pid, msg))
    stream.flush()
    
# -------------------------------------------------------------------- #

def log(msg, process = None):
    log_write(msg, process, sys.stdout)

# -------------------------------------------------------------------- #

def error(msg, process = None):
    log_write(msg, process, sys.stderr)

# -------------------------------------------------------------------- #

def processCommunicateTarget(process):
    _, err = process.communicate()
    if process.returncode != 0:
        error(err[:-1])            
        error("Command failed. Sorry")

# -------------------------------------------------------------------- #

def processCommunicateLive(process, on_output = None, on_error = None):
    while True:
        out = process.stdout.readline()
        err = process.stderr.readline()
        if (out == "") and (err == "") and (process.poll() is not None):
            break
        if (out != "") and (on_output is not None):
            on_output(out[:-1], process)
        if (err != "") and (on_error is not None):
            on_error(err[:-1], process)

# -------------------------------------------------------------------- #

def waitForProcesses(processes, wait_timeout = None, on_output = None, on_error = None):
    '''
    Wait for a group of processes to finish, but run them in parallel.
    '''
    log("Waiting for processes: %s" % [process.pid for process in processes])    
    threads = []
    start_times = []
    for process in processes:
        thread = threading.Thread(target=processCommunicateLive, args=(process,on_output,on_error))
        threads.append(thread)
        thread.start()

    all_ok = True
    elapsed = 0
    while elapsed < wait_timeout:
        num_remaining_processes = len(processes)
        i = 0
        while i < num_remaining_processes:
            process = processes[i]
            thread = threads[i]
            if not thread.is_alive():
                if process.returncode != 0:
                    error("Process %u exited with error code %u (elapsed: %.2lf)" % (process.pid, process.returncode, elapsed))
                    all_ok = False
                else:
                    log("Process %u finished successfully (elapsed: %.2lf)" % (process.pid, elapsed))
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
    for thread in threads:
        error("Process %u got timeout (%.2lf)." % (process.pid, wait_timeout))
        all_ok = False
    return all_ok

# -------------------------------------------------------------------- #

def executeCommand(command):
    log("Running command: %s" % command)
    process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process

# -------------------------------------------------------------------- #

def executeRemoteCommand(servers, command, user = None):
    processes = []
    for server in servers:
        remote = server if user is None else "%s@%s" % (user, server)
        process = executeCommand("ssh %s -C \"%s\"" % (remote, command))
        processes.append(process)
    return processes

# -------------------------------------------------------------------- #

def copyToRemote(servers, sources, remote_dir, user = None):
    processes = []    
    for server in servers:
        remote = server if user is None else "%s@%s" % (user, server)
        remote_copy_cmd = "scp -r " + " ".join(sources) + " %s:%s" % (remote, remote_dir)
        process = executeCommand(remote_copy_cmd)
        processes.append(process)
    return processes


###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
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
            
    waitForProcesses(processes, 5, log, error)    