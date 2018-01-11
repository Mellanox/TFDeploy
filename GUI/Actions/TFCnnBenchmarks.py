#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import tempfile
from Util import *
from Step import Step

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
    
    ATTRIBUTES = [["PS", ["12.12.12.25"]],
                  ["Workers", ["12.12.12.26"]],
                  ["Base Port", 5000],
                  ["Script", "~/benchmarks/scripts/tf_cnn_benchmarks/"],
                  ["Model", "trivial"],
                  ["Batch Size", 32],
                  ["Num GPUs", 2],
                  ["Server Protocol", "grpc+verbs"],
                  ["Data Dir", "/data/imagenet_data/"],
                  ["Debug Level", 0]]

    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        Step.__init__(self, values)
        self._on_output = lambda s: log(s[:-1])

    # -------------------------------------------------------------------- #

    def ps(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_PS]
    
    def workers(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_WORKERS]
    
    def base_port(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_BASE_PORT]
    
    def script(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_SCRIPT]
    
    def model(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_MODEL]
    
    def batch_size(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_BATCH_SIZE]
    
    def num_gpus(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_NUM_GPUS]
    
    def server_protocol(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_SERVER_PROTOCOL]

    def data_dir(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_DATA_DIR]
    
    def log_level(self):
        return self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_LOG_LEVEL]
    
    # -------------------------------------------------------------------- #
    
    def __getitem__(self, key):
        return self._values[key]
    
    # -------------------------------------------------------------------- #
    
    def __repr__(self):
        return TFCnnBenchmarksStep.NAME
            
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
        process = executeRemoteCommand([ip], command)[0]
        return process
         
# -------------------------------------------------------------------- #

    def perform(self):
        title("Running tf_cnn_benchmarks.py", UniBorder.BORDER_STYLE_STRONG)
    
        work_dir_name = "tmp." + next(tempfile._get_candidate_names()) + next(tempfile._get_candidate_names())
        work_dir = os.path.join(tempfile._get_default_tempdir(), work_dir_name)
        script_dir = os.path.dirname(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_SCRIPT]) 
        
        print "Work dir: %s" % work_dir
        print "Secript dir: %s" % script_dir 
    
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
        servers = list(set(self.ps() + self.workers()))
    
        #########
        # Copy: #
        #########
        title("Copying scripts:", UniBorder.BORDER_STYLE_SINGLE)    
        processes = copyToRemote(servers, [script_dir], work_dir, user=None)
        res = waitForProcesses(processes, 10, log, error)
        if not res:
            sys.exit(1)
    
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
        res = waitForProcesses(processes, 300, log, error)
        if not res:
            sys.exit(1)
        
        ############
        # Cleanup: #
        ############
        title("Cleaning:", UniBorder.BORDER_STYLE_SINGLE)
        processes = executeRemoteCommand(servers, "rm -rf %s" % work_dir, user=None)
        waitForProcesses(processes, 10, log, error)
        
        log("All done.")

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
    step = TFCnnBenchmarksStep()
    step.perform()

