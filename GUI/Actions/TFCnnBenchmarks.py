#!/usr/bin/python
# -*- coding: utf-8 -*-

from getpass import getuser, getpass
import os
import tempfile
from Util import *
from Step import Step
from Actions.TestEnvironment import TestEnvironment
from Actions.Util import executeRemoteCommand
from Actions.FormattedTable import FormattedTable
import sys
import re

###############################################################################

class PerformanceMeasurement(object):
    def __init__(self):
        self.avg = 0.0
        self.min = 0.0
        self.max = 0.0

class PerformanceReuslts(object):
    def __init__(self):
        self.cpu = PerformanceMeasurement()
        self.gpu = PerformanceMeasurement()
        self.mem = PerformanceMeasurement()
        self.tx_bytes = PerformanceMeasurement()
        self.rx_bytes = PerformanceMeasurement()
        self.images_sec = PerformanceMeasurement()
     
###############################################################################

@Step.REGISTER()
class TFCnnBenchmarksStep(Step):
    
    NAME = "TF CNN Benchmarks"
    
    ATTRIBUTE_ID_PS = 0
    ATTRIBUTE_ID_WORKERS = 1
    ATTRIBUTE_ID_BASE_PORT = 2
    ATTRIBUTE_ID_SCRIPT = 3
    ATTRIBUTE_ID_MODEL = 4
    ATTRIBUTE_ID_BATCH_SIZE = 5
    ATTRIBUTE_ID_NUM_GPUS = 6
    ATTRIBUTE_ID_SERVER_PROTOCOL = 7
    ATTRIBUTE_ID_DATA_DIR = 8
    ATTRIBUTE_ID_LOG_LEVEL = 9
    
    ATTRIBUTES = [["PS", "12.12.12.25", "12.12.12.26"],
                  ["Workers", "12.12.12.25", "12.12.12.26"],
                  ["Base Port", "5000"],
                  ["Script", "~/benchmarks/scripts/tf_cnn_benchmarks/"],
                  ["Model", "vgg16"],
                  ["Batch Size", "32"],
                  ["Num GPUs", "2"],
                  ["Server Protocol", "grpc+verbs"],
                  ["Data Dir", "/data/imagenet_data/"],
                  ["Log Level", "0"]]

    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        Step.__init__(self, values)
        self._stopping = False
        self._processes = []
        self._openPerformanceFile()        

    # -------------------------------------------------------------------- #

    def ps(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_PS].split(",")
    
    def workers(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_WORKERS].split(",")
    
    def base_port(self):
        return int(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_BASE_PORT])
    
    def script(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_SCRIPT]
    
    def model(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_MODEL]
    
    def batch_size(self):
        return int(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_BATCH_SIZE])
    
    def num_gpus(self):
        return int(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_NUM_GPUS])
    
    def server_protocol(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_SERVER_PROTOCOL]

    def data_dir(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_DATA_DIR]
    
    def log_level(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_LOG_LEVEL]
    
    # -------------------------------------------------------------------- #
    
    def __repr__(self):
        return "%s [%s, %s, %u GPUs, batch %u]" % (TFCnnBenchmarksStep.NAME,
                                                   self.model(),
                                                   self.server_protocol(),
                                                   self.num_gpus(),
                                                   self.batch_size()) 

    # -------------------------------------------------------------------- #
    
    def _openPerformanceFile(self):
        performance_file_path = os.path.join(TestEnvironment.logsFolder(), "performance.csv")
        first_time = not os.path.exists(performance_file_path)
        self._performance_file = open(performance_file_path, "a+")
        if first_time:
            self._performance_file.write("%-30s, %-12s, %-5s, %-14s, %-11s, %-8s, %-3s, %-10s\n"
                                         % ("Date", "Model", "Batch", "Protocol", "GPUs/Server", "#Workers", "#PS", "Images/sec"))
            self._performance_file.flush()

    # -------------------------------------------------------------------- #
    
    def _appendToPerformanceFile(self):
        ''' Overall step performance (average all workers). '''
        n = len(self._performance_results)
        avg_images_sec = 0.0
        avg_cpu = 0.0
        avg_gpu = 0.0
        for process in self._processes:
            avg_images_sec += process.results.images_sec.avg
            avg_cpu += process.results.cpu.avg
            avg_gpu += process.results.gpu.avg
        avg_images_sec /= n
        avg_cpu /= n
        avg_gpu /= n
        
        self._performance_file.write("%-30s, %-12s, %-5u, %-14s, %-11u, %-8u, %-3u, %-10s\n"
                                     % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                        self.model(),
                                        self.batch_size(),
                                        self.server_protocol(),
                                        self.num_gpus(),
                                        len(self.workers()),
                                        len(self.ps()),
                                        avg_images_sec))
        self._performance_file.close()

    # -------------------------------------------------------------------- #
    
    def _runJob(self, work_dir, ip, job_name, task_id):
        command = ""
        command += " TF_PS_HOSTS=%s" % ",".join(self._cluster_ps)
        command += " TF_WORKER_HOSTS=%s" % ",".join(self._cluster_workers)
        command += " TF_MODEL=%s" % self.model()
        command += " TF_NUM_GPUS=%s" % self.num_gpus()
        command += " TF_BATCH_SIZE=%s" % self.batch_size()
        command += " TF_SERVER_PROTOCOL=%s" % self.server_protocol()
        command += " TF_CPP_MIN_VLOG_LEVEL=%s" % self.log_level()
        command += " TF_DATA_DIR=%s" % self.data_dir()
        command += " DEVICE_IP=%s" % ip
        command += " %s/run_job.sh %s %u" % (work_dir, job_name, task_id)
        title = "[%s] %s - %u" % (ip, job_name, task_id)
        log_file_name = "%s_%u.log" % (job_name, task_id)
        log_file_path = os.path.join(TestEnvironment.logsFolder(), log_file_name)
        factory = BasicProcess.getFactory(title, log_file_path)
        process = executeRemoteCommand([ip], command, factory = factory)[0]
        self._processes.append(process)
        return process

    # -------------------------------------------------------------------- #
    
    def _onOut(self, line, process):
        if "PROCESS ID: " in line:
            process.remote_pid = int(line.split("PROCESS ID: ")[1])
            process.gpu_monitor = TestEnvironment.getGPUMonitor(process.server)
            process.cpu_monitor = TestEnvironment.getCPUMonitor(process.server, process.remote_pid) 
        elif "Img/sec" in line:
            log("Server %s: starting monitors." % process.server, process)
            process.gpu_monitor.start()
            process.cpu_monitor.start()
            process.results = PerformanceReuslts()
            line = "%-7s, %-4s, %-5s, %-12s, %-12s, %-5s, %-6s, %-6s" % ("CPU", "MEM", "GPU", "RX/TX (Mbit)", "images/sec", "+/-", "jitter", "loss")
            log(line, process)
        elif "images/sec" in line:
            if "total " in line:
                log("Server %s: stopping monitors." % process.server, process)
                process.cpu_monitor.stop()
                process.gpu_monitor.stop()
            else:
                # https://regex101.com/
                m = re.match("([0-9]+)\s+images\/sec: ([0-9\.]+) \+\/- ([0-9\.]+) \(jitter = ([0-9\.]+)\)\s+([0-9\.]+)", line)
                if m is None:
                    print "Error: Regex match failed. Please contact the developers to fix it."
                    sys.exit(1)
                    
                step = int(m.group(1))
                images_sec = float(m.group(2))
                deviation = float(m.group(3))
                jitter = float(m.group(4))
                loss = float(m.group(5))
                    
                gpu_val = None
                while gpu_val is None:
                    gpu_val = process.gpu_monitor.get()
                cpu_val = None
                while cpu_val is None:
                    cpu_val = process.cpu_monitor.get()
                    
                _, _, _, process.results.gpu.avg, process.results.gpu.min, process.results.gpu.max = gpu_val 
                _, _, _, process.results.cpu.avg, process.results.cpu.min, process.results.cpu.max = cpu_val
                
                line = "%-7.2lf, %-4.1lf, %-5.2lf, %-12s, %-12.2lf, %-5.2lf, %-6.2lf, %-6.2lf" % (process.results.cpu.avg, 0.0, process.results.gpu.avg, "%u/%u" % (0, 0), images_sec, deviation, jitter, loss)
                log(line, process)
        else:
            log(line, process)                
            
    # -------------------------------------------------------------------- #

    def _onJobDone(self, process):
        handler = TestEnvironment.onProcessDone()
        if handler is not None:
            handler(process)
        self._stopAll(process)
        
    # -------------------------------------------------------------------- #

    def _stopAll(self, process):
        #TODO: lock
        if self._stopping:
            return
        self._stopping = True
        log("Stopping remaining processes...")
        time.sleep(5)
        self.runInline("%s/clean_host.sh" % self._work_dir, self._servers)
         
# -------------------------------------------------------------------- #

    def perform(self):
        work_dir_name = "tmp." + next(tempfile._get_candidate_names()) + next(tempfile._get_candidate_names())
        work_dir = os.path.join(tempfile._get_default_tempdir(), work_dir_name)
        script_dir = os.path.dirname(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_SCRIPT]) 
        
        user = getuser()
        self._work_dir = work_dir
        self._servers = list(set(self.ps() + self.workers()))
            
        #########################
        # Kill other instances: #
        #########################
        kill_cmd = "ps -ef | grep tf_cnn_benchmarks.py | grep -v grep | grep %s | grep -v %s | sed -e 's@%s *\\([0-9]\\+\\) .*@\\1@g' | xargs kill -9" % (user, work_dir, user)
        res = self.runInline(kill_cmd, self._servers, wait_timeout = 5)
        if not res:
            return False
        
        ##################
        # Build cluster: #
        ##################
        port = self.base_port()
        self._cluster_ps = []
        self._cluster_workers = []
        for ip in self.ps():
            self._cluster_ps.append("%s:%u" % (ip, port))
            port += 1
        for ip in self.workers():
            self._cluster_workers.append("%s:%u" % (ip, port))
            port += 1        
    
        #########
        # Copy: #
        #########
        title("Copying scripts:", UniBorder.BORDER_STYLE_SINGLE)    
        res = self.runSCP(self._servers, [script_dir], work_dir, wait_timeout = 10)
        if not res:
            return False
    
        ########
        # Run: #
        ########
        title("Running:", UniBorder.BORDER_STYLE_SINGLE)
        processes = []
        for i in range(len(self.ps())):
            ip = self.ps()[i]
            process = self._runJob(work_dir, ip, "ps", i)
            processes.append(process)
        for i in range(len(self.workers())):
            ip = self.workers()[i]
            process = self._runJob(work_dir, ip, "worker", i)
            processes.append(process)
        res = waitForProcesses(processes, 
                               wait_timeout=300, 
                               on_output=self._onOut, 
                               on_error=TestEnvironment.onErr(),
                               on_process_start=TestEnvironment.onNewProcess(),
                               on_process_done=self._onJobDone)
        if not res:
            return False
        
        ############
        # Cleanup: #
        ############
        title("Cleaning:", UniBorder.BORDER_STYLE_SINGLE)
        processes = executeRemoteCommand(self._servers, "rm -rf %s" % work_dir)
        waitForProcesses(processes, wait_timeout=10)
        
        self._appendToPerformanceFile()
        return True

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
    TestEnvironment.setOnOut(log)
    TestEnvironment.setOnErr(error)
    logs_dir = os.path.join("/tmp", "test_logs")
    TestEnvironment.setLogsFolder(logs_dir)
    if not os.path.exists(logs_dir):
        os.makedirs(TestEnvironment.logsFolder())
    step = TFCnnBenchmarksStep()
    step.perform()

