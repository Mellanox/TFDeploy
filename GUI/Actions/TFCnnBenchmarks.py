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
from GPUMonitor import Measurement, Monitor, GPUSampler,\
    CPUAndMemSampler, RXTXSampler, CommonPerformanceMeasurements

###############################################################################

class TFPerformanceMeasurements(CommonPerformanceMeasurements):
    def __init__(self):
        super(TFPerformanceMeasurements, self).__init__()
        self.images_sec = Measurement("IMG/SEC")
        
    # -------------------------------------------------------------------- #
    
    def reduce(self, other):
        CommonPerformanceMeasurements.reduce(self, other)
        self.images_sec.reduce(other.images_sec)
        
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
    
    ATTRIBUTES = [["PS", "12.12.12.25"],
                  ["Workers", "12.12.12.26"],
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
        self._processes = []
        self._perf = TFPerformanceMeasurements()
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
        self._performance_table = FormattedTable()
        self._performance_table.add_column(FormattedTable.Column("Date", 20))
        self._performance_table.add_column(FormattedTable.Column("Benchmark", 20))
        self._performance_table.add_column(FormattedTable.Column("Model", 12))
        self._performance_table.add_column(FormattedTable.Column("Batch", 5))
        self._performance_table.add_column(FormattedTable.Column("Protocol", 14))
        self._performance_table.add_column(FormattedTable.Column("GPUs/Server", 11))
        self._performance_table.add_column(FormattedTable.Column("#Workers", 8))
        self._performance_table.add_column(FormattedTable.Column("#PS", 3))
        self._performance_table.add_column(FormattedTable.Column("Images/sec", 10))
        self._performance_table.add_column(FormattedTable.Column("CPU", 7))
        self._performance_table.add_column(FormattedTable.Column("GPU", 5))
        self._performance_table.add_column(FormattedTable.Column("MEM", 5))
        self._performance_table.add_column(FormattedTable.Column("RX/TX (Mbit/sec)", 16))
        self._performance_table.add_column(FormattedTable.Column("Max RX/TX (Mbit/sec)", 19))
        self._performance_table.bind(self._performance_file, first_time)
                
    # -------------------------------------------------------------------- #
    
    def _appendToPerformanceFile(self):
        ''' Overall step performance (average all workers). '''
        
        log("Appending to results file: %s" % self._performance_file.name) 
        row = [time.strftime("%Y-%m-%d %H:%M:%S"),
               "TF cnn benchmarks",
               self.model(),
               self.batch_size(),
               self.server_protocol(),
               self.num_gpus(),
               len(self.workers()),
               len(self.ps()),
               "%.2lf" % self._perf.images_sec.avg,               
               "%.2lf" % self._perf.cpu.avg,
               "%.2lf" % self._perf.gpu.avg,
               "%.2lf" % self._perf.mem.avg,
               "%.2lf/%.2lf" % (self._perf.rx.rate.avg, self._perf.tx.rate.avg),
               "%.2lf/%.2lf" % (self._perf.rx.rate.max, self._perf.tx.rate.max)]
        self._performance_table.add_row(row)
        self._performance_table.unbind()
        self._performance_file.close()

    # -------------------------------------------------------------------- #
    
    def _startProcessMonitors(self, process):
        file_base = os.path.splitext(process.log_file_path)[0]
        process.cpu_graph = open(file_base + ".cpu.csv", "w")
        process.gpu_graph = open(file_base + ".gpu.csv", "w")
        log("Server %s: starting monitors:\n"
            "   + CPU: %s\n"
            "   + GPU: %s"
             % (process.server, process.cpu_graph.name, process.gpu_graph.name), process)

        process.gpu_monitor = Monitor(process.server, process.gpu_graph, time_interval = 0, log_ratio = 1)
        process.gpu_monitor.addSampler(GPUSampler())
        process.common_monitor = Monitor(process.server, process.cpu_graph, time_interval = 0.1, log_ratio = 1)
        process.common_monitor.addSampler(CPUAndMemSampler(process.remote_pid))
        process.common_monitor.addSampler(RXTXSampler(process.rdma_device, process.rdma_port))

        process.perf = TFPerformanceMeasurements()                        
        process.perf.gpu = process.gpu_monitor["GPU-0"]
        process.perf.cpu = process.common_monitor["CPU"]
        process.perf.mem = process.common_monitor["MEM"]
        process.perf.rx = process.common_monitor["RDTA"]
        process.perf.tx = process.common_monitor["TDTA"]
        process.perf.images_sec = Measurement("IMG/SEC")

        process.gpu_monitor.start()
        process.common_monitor.start()
        
        process.table = FormattedTable()
        process.table.add_column(FormattedTable.Column("STEP", 4))
        process.table.add_column(FormattedTable.Column("CPU", 7))
        process.table.add_column(FormattedTable.Column("MEM", 5))
        process.table.add_column(FormattedTable.Column("GPU", 5))
        process.table.add_column(FormattedTable.Column("RX/TX (MBit/sec)", 12))
        process.table.add_column(FormattedTable.Column("Max RX/TX (MBit/sec)", 12))
        process.table.add_column(FormattedTable.Column("images/sec", 12))
        process.table.add_column(FormattedTable.Column("+/-", 7))
        process.table.add_column(FormattedTable.Column("jitter", 6))
        process.table.add_column(FormattedTable.Column("loss", 6))
        process.table.bind(sys.stdout)        

    # -------------------------------------------------------------------- #
    
    def _stopProcessMonitors(self, process):
        process.common_monitor.stop()
        process.gpu_monitor.stop()
        process.cpu_graph.close()
        process.gpu_graph.close()
                
        row = ["---",
               "%.2lf" % process.perf.cpu.avg, 
               "%.2lf" % process.perf.mem.val, 
               "%.2lf" % process.perf.gpu.avg, 
               "%.2lf/%.2lf" % (process.perf.rx.rate.avg, process.perf.tx.rate.avg), 
               "%.2lf/%.2lf" % (process.perf.rx.rate.max, process.perf.tx.rate.max),
               "%.2lf" % process.perf.images_sec.avg, 
               "---", 
               "---", 
               "---"]
        process.table.add_bar()
        process.table.add_row(row)
        process.table.unbind()

        log("Server %s: stopped monitors." % process.server, process)

        # Append to global performance results:
        self._perf.reduce(process.perf)

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
        command += " %s/run_job2.sh %s %u" % (work_dir, job_name, task_id)
        title = "[%s] %s - %u" % (ip, job_name, task_id)
        log_file_name = "%s_%u.log" % (job_name, task_id)
        log_file_path = os.path.join(TestEnvironment.logsFolder(), log_file_name)
        factory = BasicProcess.getFactory(title, log_file_path)
        process = executeRemoteCommand([ip], command, factory = factory)[0]
        process.is_worker = job_name == "worker"
        self._processes.append(process)
        return process

    # -------------------------------------------------------------------- #
    
    def _onOut(self, line, process):
        if "PROCESS ID: " in line:
            process.remote_pid = int(line.split("PROCESS ID: ")[1])
        elif "RDMA device: " in line:
            process.rdma_device = line.split("RDMA device: ")[1]
        elif "RDMA port: " in line:
            process.rdma_port = int(line.split("RDMA port: ")[1])
        elif "Img/sec" in line:
            self._startProcessMonitors(process)
        elif "images/sec" in line:
            if "total " in line:
                self._stopProcessMonitors(process)
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
                
                process.perf.images_sec.update(images_sec)
                row = ["%u" % step,
                       "%.2lf" % process.perf.cpu.avg, 
                       "%.2lf" % process.perf.mem.val, 
                       "%.2lf" % process.perf.gpu.avg, 
                       "%.2lf/%.2lf" % (process.perf.rx.rate.avg, process.perf.tx.rate.avg), 
                       "%.2lf/%.2lf" % (process.perf.rx.rate.max, process.perf.tx.rate.max),
                       "%.2lf" % process.perf.images_sec.avg,
                       "%.2lf" % images_sec, 
                       "%.2lf" % deviation, 
                       "%.2lf" % jitter, 
                       "%.2lf" % loss]
                process.table.add_row(row)
        elif "---------------" in line:
            pass
        else:
            log(line, process)                
            
    # -------------------------------------------------------------------- #

    def _onJobDone(self, process):
        handler = TestEnvironment.onProcessDone()
        if handler is not None:
            handler(process)
            
        self._processes.remove(process)
        if not self._stopping:
            self._stopping = True  #TODO: lock
            self._stopAll(process)
        
        return process.instance.returncode in [0, 143]
        
    # -------------------------------------------------------------------- #

    def _stopAll(self, process):
        log("Stopping remaining processes...")
        wait_time_for_workers_to_exit_gracefully = len(self.workers()) - 1 if process.is_worker else 0
        time.sleep(wait_time_for_workers_to_exit_gracefully)
        
        for process in self._processes:
            self.runInline("kill -15 %u" % process.remote_pid, servers=[process.server])
         
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

        self._appendToPerformanceFile()
        
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
    logs_dir = os.path.join("/tmp", "test_logs")
    TestEnvironment.setLogsFolder(logs_dir)
    if not os.path.exists(logs_dir):
        os.makedirs(TestEnvironment.logsFolder())
    step = TFCnnBenchmarksStep()
    step.perform()

