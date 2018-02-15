#!/usr/bin/python
# -*- coding: utf-8 -*-

from getpass import getuser
import tempfile
from Step import Step
import sys
import re
from Monitor import Measurement, CommonPerformanceMeasurements
from RemoteMonitor import RemoteMonitor
import os
import time
import signal

from TestEnvironment import TestEnvironment
from Common.FormattedTable import FormattedTable
from Common.Log import LogWriter, LOG_LEVEL_NOTE, LOG_LEVEL_INFO, log, title,\
    error, UniBorder
from Common.Util import BasicProcess, executeRemoteCommand, waitForProcesses

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
    
    ATTRIBUTES = [["PS", "12.12.12.25,12.12.12.26"],
                  ["Workers", "12.12.12.25,12.12.12.26"],
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
        self._perf = TFPerformanceMeasurements()

    # -------------------------------------------------------------------- #

    def ps(self):
        return os.path.expandvars(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_PS]).split(",")
    
    def workers(self):
        return os.path.expandvars(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_WORKERS]).split(",")
    
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
    
    def attributesRepr(self):
        return "%s, %s, %u GPUs, batch %u" % (self.model(),
                                              self.server_protocol(),
                                              self.num_gpus(),
                                              self.batch_size()) 

    # -------------------------------------------------------------------- #
    
    def _openPerformanceFile(self):
        performance_file_path = os.path.join(TestEnvironment.Get().testLogsDir(), "results.csv")
        first_time = not os.path.exists(performance_file_path)
        self._performance_file = open(performance_file_path, "a+")
        self._performance_table = FormattedTable()
        self._performance_table.addColumn(FormattedTable.Column("Date", 20), "Info")
        self._performance_table.addColumn(FormattedTable.Column("Benchmark", 20), "Info")
        self._performance_table.addColumn(FormattedTable.Column("Model", 12), "Info")
        self._performance_table.addColumn(FormattedTable.Column("Batch", 5), "Info")
        self._performance_table.addColumn(FormattedTable.Column("Protocol", 14), "Info")
        self._performance_table.addColumn(FormattedTable.Column("GPUs/Server", 11), "Info")
        self._performance_table.addColumn(FormattedTable.Column("#Workers", 8), "Info")
        self._performance_table.addColumn(FormattedTable.Column("#PS", 3), "Info")
        self._performance_table.addColumn(FormattedTable.Column("Images/sec", 10), "Performance")
        self._performance_table.addColumn(FormattedTable.Column("CPU%", 7), "Performance")
        self._performance_table.addColumn(FormattedTable.Column("MEM%", 5), "Performance")
        self._performance_table.addColumn(FormattedTable.Column("GPU%", 5), "Performance")
        self._performance_table.addColumn(FormattedTable.Column("Average", 18), "RX/TX rate (Mbit/sec)")
        self._performance_table.addColumn(FormattedTable.Column("Max", 18), "RX/TX rate (Mbit/sec)")
        self._performance_table.addColumn(FormattedTable.Column("Buffer overrun"), "Network Errors")
        self._performance_table.addColumn(FormattedTable.Column("TX discards"), "Network Errors")
        self._performance_table.addColumn(FormattedTable.Column("RX errors"), "Network Errors")
        self._performance_table.addColumn(FormattedTable.Column("RX constraint errors"), "Network Errors")
        self._performance_table.bind(self._performance_file, type = FormattedTable.TYPE_CSV, print_header = first_time)
                
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
               "%.2lf" % self._perf.mem.avg,
               "%.2lf" % self._perf.gpu.avg,
               "%.2lf/%.2lf" % (self._perf.rx.rate.avg, self._perf.tx.rate.avg),
               "%.2lf/%.2lf" % (self._perf.rx.rate.max, self._perf.tx.rate.max),
               self._perf.net_erros.excessive_buffer_overrun_errors.val,
               self._perf.net_erros.port_xmit_discards.val,
               self._perf.net_erros.port_rcv_errors.val,
               self._perf.net_erros.port_rcv_constraint_errors.val]
        self._performance_table.addRow(row)
        self._performance_table.unbind()
        self._performance_file.close()
        
        summary_table = self._performance_table.cut(["Performance", "RX/TX rate (Mbit/sec)", "Network Errors"])                 
        summary_table.printFormatted(LogWriter(None, LOG_LEVEL_NOTE))

    # -------------------------------------------------------------------- #
    
    def _startProcessMonitors(self, process):
        log("Server %s: Starting monitors." % process.server)
        process.graph_dir = os.path.join(self._logs_dir, "graphs", "worker_%u" % process.task_id)
        process.remote_graph_dir = os.path.join(self._work_dir, "graphs")
        if not os.path.exists(process.graph_dir):
            os.makedirs(process.graph_dir)
        remote_monitor_title = lambda process: "Monitor [%s]" % process.server 
        remote_monitor_bin = os.path.join(self._work_dir, "Monitor.py")
        remote_monitor_flags = "--cpu %u 0 --gpu 0 --net %s %u 0.05 --net_errors %s %u 1 -d %s" % (process.remote_pid, 
                                                                                                   process.rdma_device, process.rdma_port,
                                                                                                   process.rdma_device, process.rdma_port,
                                                                                                   process.remote_graph_dir)
        process.monitor_log_path = os.path.join(process.graph_dir, "monitor.log") 
        process.monitor = RemoteMonitor(process.server, remote_monitor_bin, remote_monitor_flags, remote_monitor_title, process.monitor_log_path)
        
        process.monitor.start()
        process.perf = TFPerformanceMeasurements()                        
        process.perf.images_sec = Measurement("IMG/SEC")
        
        process.table = FormattedTable()
        process.table.addColumn(FormattedTable.Column("STEP", 4))
        process.table.addColumn(FormattedTable.Column("CPU%", 7))
        process.table.addColumn(FormattedTable.Column("MEM%", 5))
        process.table.addColumn(FormattedTable.Column("GPU%", 5))
        process.table.addColumn(FormattedTable.Column("RX/TX (MBit/sec)", 12))
        process.table.addColumn(FormattedTable.Column("Max RX/TX (MBit/sec)", 12))
        process.table.addColumn(FormattedTable.Column("images/sec", 12))
        process.table.addColumn(FormattedTable.Column("+/-", 7))
        process.table.addColumn(FormattedTable.Column("jitter", 6))
        process.table.addColumn(FormattedTable.Column("loss", 6))
        log_level = LOG_LEVEL_NOTE if process.is_worker and process.task_id == 0 else LOG_LEVEL_INFO
        process.table.bind(LogWriter(process, log_level))

    # -------------------------------------------------------------------- #
    
    def _stopProcessMonitors(self, process):
        log("Server %s: stopping monitors..." % process.server)        
        process.monitor.stop()
        process.monitor.fillMeasurement(process.perf.cpu)
        process.monitor.fillMeasurement(process.perf.mem)
        process.monitor.fillMeasurement(process.perf.rx)
        process.monitor.fillMeasurement(process.perf.tx)
        process.monitor.fillMeasurement(process.perf.net_erros.excessive_buffer_overrun_errors)
        process.monitor.fillMeasurement(process.perf.net_erros.port_xmit_discards)
        process.monitor.fillMeasurement(process.perf.net_erros.port_rcv_errors)
        process.monitor.fillMeasurement(process.perf.net_erros.port_rcv_constraint_errors)
        for gpu_id in process.monitor.search("GPU"):
            gpu = Measurement(gpu_id)
            process.monitor.fillMeasurement(gpu)
            process.perf.gpu.reduce(gpu)
        process.monitor.close()

        self.runInline("scp %s:%s/* %s" % (process.server, process.remote_graph_dir, process.graph_dir))            
                
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
        process.table.addBar()
        process.table.addRow(row)
        process.table.unbind()

        log("Server %s: monitors stopped." % process.server)

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
        log_file_path = os.path.join(self._logs_dir, "%s_%u.log" % (job_name, task_id))
        factory = BasicProcess.getFactory(title, log_file_path)
        server = TestEnvironment.Get().getServer(ip)
        process = executeRemoteCommand([server], command, factory = factory)[0]
        process.name = "%s_%u" % (job_name, task_id)
        process.task_id = task_id
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
                m = re.match("total images\/sec: ([0-9\.]+)", line)
                if m is None:
                    print "Error: Regex match failed. Please contact the developers to fix it."
                    sys.exit(1)
                images_sec = float(m.group(1))
                process.perf.images_sec.val = images_sec
                process.perf.images_sec.total = images_sec
                process.perf.images_sec.min = images_sec
                process.perf.images_sec.max = images_sec
                process.perf.images_sec.count = 1
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
                perf = process.monitor.get(["CPU.avg", "MEM.val", "RDTA.rate.avg", "RDTA.rate.max", "TDTA.rate.avg", "TDTA.rate.max"])
                gpu_perf = process.monitor.get(["%s.avg" % gpu for gpu in process.monitor.search("GPU")])
                process.perf.images_sec.update(images_sec)

                try:
                    cpu = float(perf[0])
                    mem = float(perf[1])
                    rx_rate_avg = float(perf[2])
                    rx_rate_max = float(perf[3])
                    tx_rate_avg = float(perf[4])
                    tx_rate_max = float(perf[5])
                    gpu = sum([float(x) for x in gpu_perf]) / len(gpu_perf)
                except:
                    error("Server %s: Remote monitor process failed. See %s for more info." % (process.server, process.monitor_log_path))
                    raise
                
                row = ["%u" % step,
                       "%.2lf" % cpu, 
                       "%.2lf" % mem, 
                       "%.2lf" % gpu,
                       "%.2lf/%.2lf" % (rx_rate_avg, tx_rate_avg), 
                       "%.2lf/%.2lf" % (rx_rate_max, tx_rate_max),
                       "%.2lf" % images_sec, 
                       "%.2lf" % deviation, 
                       "%.2lf" % jitter, 
                       "%.2lf" % loss]
                process.table.addRow(row)
        elif "---------------" in line:
            pass
        else:
            log(line, process)                
            
    # -------------------------------------------------------------------- #

    def _onJobDone(self, process):
        handler = TestEnvironment.onProcessDone()
        if handler is not None:
            handler(process)
            
        if not self._stopping:
            self._stopping = True            
            log("Stopping remaining processes...")
            wait_time_for_workers_to_exit_gracefully = len(self.workers()) - 1
            time.sleep(wait_time_for_workers_to_exit_gracefully)
            self._stopAll()
        return process.instance.returncode in [0, 143, -15]
        
    # -------------------------------------------------------------------- #

    def _stopAll(self):
        log("Stopping processes...")
        for process in self._processes:
            if process.isAlive():
                log("   + [%s] %s: %u" % (process.server, process.name, process.instance.pid))            
                self.runInline("kill -15 %u >& /dev/null" % process.remote_pid, servers=[process.server], verbose=False)
        log("Done.")
         
    # -------------------------------------------------------------------- #

    def perform(self, index):
        Step.perform(self, index)
        self._stopping = False
        work_dir_name = "tmp." + next(tempfile._get_candidate_names()) + next(tempfile._get_candidate_names())
        work_dir = os.path.join(tempfile._get_default_tempdir(), work_dir_name)
        script_dir = os.path.dirname(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_SCRIPT]) 
        
        user = getuser()
        self._work_dir = work_dir
        self._servers = TestEnvironment.Get().getServers(list(set(self.ps() + self.workers())))
            
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
        self._openPerformanceFile()
        
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
                               wait_timeout=600,
                               on_output=self._onOut,
                               on_process_start=TestEnvironment.onNewProcess(),
                               on_process_done=self._onJobDone)
        if not res or self._stop:
            return False

        self._appendToPerformanceFile()
        
        ############
        # Cleanup: #
        ############
        title("Cleaning:", UniBorder.BORDER_STYLE_SINGLE)
        processes = executeRemoteCommand(self._servers, "rm -rf %s" % work_dir)
        waitForProcesses(processes, wait_timeout=10)
        return True

    # -------------------------------------------------------------------- #
    
    def stop(self):
        Step.stop(self)
        self._stopping = True
        self._stopAll()
        
###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

import shutil

if __name__ == '__main__':
    if os.path.isdir("/tmp/test_logs"):
        shutil.rmtree("/tmp/test_logs")        
    TestEnvironment.Get().setTestLogsDir("/tmp/test_logs")
    step = TFCnnBenchmarksStep()
    step.perform(0)

