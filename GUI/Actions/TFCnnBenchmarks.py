#!/usr/bin/python
# -*- coding: utf-8 -*-

from getpass import getuser, getpass
import os
import tempfile
from Util import *
from Step import Step
from Actions.Step import TestEnvironment
from Actions.Util import executeRemoteCommand
import sys

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
    
    ATTRIBUTES = [["PS", "12.12.12.25,12.12.12.26"],
                  ["Workers", "12.12.12.25,12.12.12.26"],
                  ["Base Port", "5000"],
                  ["Script", "~/benchmarks/scripts/tf_cnn_benchmarks/"],
                  ["Model", "trivial"],
                  ["Batch Size", "32"],
                  ["Num GPUs", "2"],
                  ["Server Protocol", "grpc+verbs"],
                  ["Data Dir", "/data/imagenet_data/"],
                  ["Log Level", "0"]]

    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        Step.__init__(self, values)
        self._stopping = False
        self._titles = {}
        self._files = {}

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
        return process

    # -------------------------------------------------------------------- #
    
    def _onOut(self, line, process):
        op = TestEnvironment.onOut()
        if op is not None:
            op(line, process)
            
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
                               on_output=TestEnvironment.onOut(), 
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
        return True

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
    TestEnvironment.setOnOut(log)
    TestEnvironment.setOnErr(error)
    TestEnvironment.setLogsFolder(os.path.join("~", "test_logs"))
    step = TFCnnBenchmarksStep()
    step.perform()

