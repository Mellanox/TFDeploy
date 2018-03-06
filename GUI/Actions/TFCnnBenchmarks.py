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

from TestEnvironment import TestEnvironment
from Common.FormattedTable import FormattedTable
from Common.Log import LogWriter, LOG_LEVEL_NOTE, LOG_LEVEL_INFO, log, title,\
    error, UniBorder
from Common.Util import BasicProcess, executeRemoteCommand, waitForProcesses,\
    toFileName
from Actions.Step import StepAttribute, DefaultAttributesWidget
import threading

###############################################################################

class ServerInfo(object):
    def __init__(self, ip):
        self.ip = ip
        self.hostname = TestEnvironment.Get().getServer(ip)
        self.processes = []
        self.monitor = None

###############################################################################

class RemoteDeviceInfo(object):
    def __init__(self):
        self.link = None
        self.name = None
        self.port = 0
        self.is_up = False

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
    
    ATTRIBUTE_ID_MODE = 0
    ATTRIBUTE_ID_ALL_REDUCE_SPECS = 1
    ATTRIBUTE_ID_CONTROLLER = 2
    ATTRIBUTE_ID_PS = 3
    ATTRIBUTE_ID_WORKERS = 4
    ATTRIBUTE_ID_BASE_PORT = 5
    ATTRIBUTE_ID_SCRIPT = 6
    ATTRIBUTE_ID_MODEL = 7
    ATTRIBUTE_ID_BATCH_SIZE = 8
    ATTRIBUTE_ID_NUM_GPUS = 9
    ATTRIBUTE_ID_SERVER_PROTOCOL = 10
    ATTRIBUTE_ID_DATA_DIR = 11
    ATTRIBUTE_ID_LOG_LEVEL = 12
    
    MODE_PARAMETER_SERVER = 0
    MODE_DISTRIBUTED_ALL_REDUCE = 1
    
    MODE_NAMES = ["Parameter Server", "Distributed All-Reduce"]
    ALL_REDUCE_SPECS = ["xring", "xring#2", "nccl", "nccl/xring", "pscpu", "psgpu#4", "pscpu:2k:pscpu#2:64k:xring", "pscpu/pscpu#2"] 
    MODELS = ["trivial", "inception3", "inception4", "resnet50", "resnet101", "resnet152", "vgg16", "vgg19"]
    PROTOCOLS = ["grpc", "grpc+verbs", "grpc+ucx"]
    
    ATTRIBUTES = [StepAttribute("Mode", MODE_NAMES[0], MODE_NAMES),
                  StepAttribute("All-Reduce Spec", ALL_REDUCE_SPECS[0], ALL_REDUCE_SPECS),
                  StepAttribute("Controller", "12.12.12.25"),
                  StepAttribute("PS", "12.12.12.25"),
                  StepAttribute("Workers", "12.12.12.25,12.12.12.26"),
                  StepAttribute("Base Port", "5000"),
                  StepAttribute("Script", "~/benchmarks/scripts/tf_cnn_benchmarks/"),
                  StepAttribute("Model", "vgg16", MODELS),
                  StepAttribute("Batch Size", "32"),
                  StepAttribute("Num GPUs", "2"),
                  StepAttribute("Server Protocol", "grpc+verbs", PROTOCOLS),
                  StepAttribute("Data Dir", "/data/imagenet_data/"),
                  StepAttribute("Log Level", "0")]

    # -------------------------------------------------------------------- #

    class AttributesWidget(DefaultAttributesWidget):
        def __init__(self, attributes, parent = None):
            super(TFCnnBenchmarksStep.AttributesWidget, self).__init__(attributes, parent = None)
        
        def _setMode(self, val):
            if val in TFCnnBenchmarksStep.MODE_NAMES:
                mode = TFCnnBenchmarksStep.MODE_NAMES.index(val)
            else:
                mode = TFCnnBenchmarksStep.MODE_NAMES[0]
                self._setFieldValue(TFCnnBenchmarksStep.ATTRIBUTE_ID_MODE, mode)
                
            is_parameter_server       = (mode == TFCnnBenchmarksStep.MODE_PARAMETER_SERVER)
            is_distributed_all_reduce = (mode == TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE)
            
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_ALL_REDUCE_SPECS, is_distributed_all_reduce)
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_CONTROLLER, is_distributed_all_reduce)
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_PS, is_parameter_server)
            
        def _onFieldChanged(self, field_index, val):
            if field_index == TFCnnBenchmarksStep.ATTRIBUTE_ID_MODE:
                self._setMode(val)
            DefaultAttributesWidget._onFieldChanged(self, field_index, val) 
            
        def load(self, values):
            DefaultAttributesWidget.load(self, values)
            mode = self._getFieldValue(TFCnnBenchmarksStep.ATTRIBUTE_ID_MODE)
            self._setMode(mode)

    # -------------------------------------------------------------------- #
    
    WIDGET_CLASS = AttributesWidget

    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        Step.__init__(self, values)
        self._stopping = False
        self._processes = []
        self._servers = {}
        self._servers_lock = threading.Lock()
        self._perf = TFPerformanceMeasurements()

    # -------------------------------------------------------------------- #

    def mode(self):
        mode_name = os.path.expandvars(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_MODE])
        return TFCnnBenchmarksStep.MODE_NAMES.index(mode_name)
    
    def all_reduce_spec(self):
        return os.path.expandvars(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_ALL_REDUCE_SPECS])

    def controller(self):
        return os.path.expandvars(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_CONTROLLER])
    
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
    
    def trace_file(self):
        return None
    
    def model_graph_file(self):
        return None
    
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
    
    def getOrCreateServer(self, ip):
        with self._servers_lock:
            if ip in self._servers:
                return self._servers[ip]
            server = ServerInfo(ip)
            self._servers[ip] = server
            return server

    # -------------------------------------------------------------------- #
    
    def _startServerMonitors(self, ip):
        log("Server %s: Starting monitors." % ip)
        server = self._servers[ip]
        server.graphs_dir = os.path.join(self._logs_dir, "graphs", toFileName(ip))
        server.remote_graphs_dir = os.path.join(self._work_dir, "graphs")
        if not os.path.exists(server.graphs_dir):
            os.makedirs(server.graphs_dir)
        remote_monitor_title = lambda process: "Monitor [%s]" % process.server 
        remote_monitor_bin = os.path.join(self._work_dir, "Monitor.py")
        
        monitored_pids = ",".join(["%u" % p.remote_pid for p in server.processes])
        monitored_nics = ",".join(["%s:%u" % (p.rdma_device.name, p.rdma_device.port) for p in server.processes])
        remote_monitor_flags = "--cpu %s 0.010 --gpu 0.020 --net %s 0.010 --net_errors %s 1 -d %s" % (monitored_pids, 
                                                                                                      monitored_nics,
                                                                                                      monitored_nics,
                                                                                                      server.remote_graphs_dir)
        server.monitor_log_path = os.path.join(server.graphs_dir, "monitor.log") 
        server.monitor = RemoteMonitor(ip, remote_monitor_bin, remote_monitor_flags, remote_monitor_title, server.monitor_log_path)
        server.monitor.start()
        for process in server.processes:
            if process.job_name != "ps":
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
    
    def _stopServerMonitors(self, ip):
        server = self._servers[ip]
        log("Server %s: stopping monitors..." % ip)
        server.monitor.stop()
        server.perf = TFPerformanceMeasurements()
        #server.monitor.fillMeasurement(server.perf.cpu)
#         server.monitor.fillMeasurement(server.perf.mem)
#         server.monitor.fillMeasurement(server.perf.rx)
#         server.monitor.fillMeasurement(server.perf.tx)
#         server.monitor.fillMeasurement(server.perf.net_erros.excessive_buffer_overrun_errors)
#         server.monitor.fillMeasurement(server.perf.net_erros.port_xmit_discards)
#         server.monitor.fillMeasurement(server.perf.net_erros.port_rcv_errors)
#         server.monitor.fillMeasurement(server.perf.net_erros.port_rcv_constraint_errors)
#         for gpu_id in server.monitor.search("GPU"):
#             gpu = Measurement(gpu_id)
#             server.monitor.fillMeasurement(gpu)
#             server.perf.gpu.reduce(gpu)
        server.monitor.close()

        self.runInline("scp %s:%s/* %s" % (server.ip, server.remote_graphs_dir, server.graphs_dir))            
                
#         row = ["---",
#                "%.2lf" % server.perf.cpu.avg, 
#                "%.2lf" % server.perf.mem.val, 
#                "%.2lf" % server.perf.gpu.avg, 
#                "%.2lf/%.2lf" % (server.perf.rx.rate.avg, server.perf.tx.rate.avg), 
#                "%.2lf/%.2lf" % (server.perf.rx.rate.max, server.perf.tx.rate.max),
#                "%.2lf" % server.perf.images_sec.avg, 
#                "---", 
#                "---", 
#                "---"]
#         server.table.addBar()
#         server.table.addRow(row)
        for process in server.processes:
            if process.job_name != "ps":
                process.table.unbind()
                # Append to global performance results:
                self._perf.reduce(process.perf)
        server.processes = []

        log("Server %s: monitors stopped." % server.ip)

    # -------------------------------------------------------------------- #
    
    def _findRemoteProcessIDs(self, processes):
        remote_process_ids = {}
        def parser(line, find_process):
            key = find_process.name
            remote_process_ids[key] = int(line.split()[1])
       
        num_attempts = 0
        max_num_attempts = 2
        while len(remote_process_ids) < len(processes):
            find_processes = []
            for process in processes:
                if process.name in remote_process_ids:
                    continue
                find_process = executeRemoteCommand([process.server], 
                                                    "ps -ef | grep %s | grep job_name=%s | grep task_index=%u | grep -v ssh" % (self._work_dir, process.job_name, process.task_id), 
                                                    verbose=True)[0]
                find_process.name = process.name
                find_processes.append(find_process)
                
            waitForProcesses(find_processes, wait_timeout=5, on_output=parser, verbose=True)
            time.sleep(1)
            num_attempts += 1
            if num_attempts == max_num_attempts:
                error("Failed to find remote process IDs. Most likely some processes failed to run.")
                break

        for process in processes:
            if process.name in remote_process_ids:
                process.remote_pid = remote_process_ids[process.name]
            else:
                process.remote_pid = -1
            log(" + [%s]: <a href='%s'>%s</a>:%*s %-5d %-5d %s" % (process.server, process.log_file_path, process.name, 10 - len(process.name), "", 
                                                                   process.instance.pid, process.remote_pid, process.command), log_level=LOG_LEVEL_NOTE)

    # -------------------------------------------------------------------- #
            
    def _getDevices(self, ips):
        links = []
        self._devices = {}
        
        def linkNameParser(line, process):
            links.append(line)
        
        def deviceNameAndPortParser(line, process):
            parts = line.split()
            res = RemoteDeviceInfo()
            res.name = parts[0]
            res.port = int(parts[2])
            res.is_up = parts[5] == "(Up)"
            self._devices[process.server] = res

        procs = []
        for ip in ips:
            server = TestEnvironment.Get().getServer(ip)
            procs.extend(executeRemoteCommand([server], "ip -o a s | grep %s | cut -d ' ' -f 2 | cut -d'.' -f1" % ip, verbose=False))
        if not waitForProcesses(procs, wait_timeout=5, on_output=linkNameParser, verbose=False):
            raise Exception("Internal Error")
        
        procs = []
        for ip in ips:
            server = TestEnvironment.Get().getServer(ip)
            i = len(procs) 
            link = links[i]
            procs.extend(executeRemoteCommand([server], "ibdev2netdev | grep %s" % link, verbose=False))
        if not waitForProcesses(procs, wait_timeout=5, on_output=deviceNameAndPortParser, verbose=False):
            raise Exception("Internal Error")

    # -------------------------------------------------------------------- #
    
    def _runJob(self, work_dir, ip, job_name, task_id):
        server = self.getOrCreateServer(ip)
        device_info = self._devices[server.hostname]
        #####################
        # Build TF command: #
        #####################
        tf_command =  ""
        
        ##################
        # Env variables: #
        ##################
        tf_command += " LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda/lib64"
        tf_command += " TF_CPP_MIN_VLOG_LEVEL=%s" % self.log_level()
        tf_command += " RDMA_DEVICE=%s" % device_info.name
        tf_command += " RDMA_DEVICE_PORT=%u" % device_info.port
        tf_command += " RDMA_GID_INDEX=3"
        tf_command += " RDMA_PKEY=0"
        tf_command += " RDMA_QUEUE_DEPTH=1024"
        tf_command += " RDMA_TIMEOUT=10"
        tf_command += " RDMA_RETRY_CNT=10"
        tf_command += " RDMA_SL=1"
        tf_command += " RDMA_MTU=512"
        tf_command += " RDMA_TRAFFIC_CLASS=8"
        tf_command += " UCX_NET_DEVICES=%s:%u" % (device_info.name, device_info.port)
        if (job_name in ["ps", "controller"]) or (self.num_gpus() == 0):
            tf_command += " CUDA_VISIBLE_DEVICES="

        ##############  
        # UCX stuff: #
        ##############
        # Ucx should be compiled ./contrib/configure-devel --enable-debug 
        #export UCX_IB_ETH_PAUSE_ON=y
        #export UCX_LOG_LEVEL=trace 

        ###############
        # GRPC Debug: #
        ###############
        #export GRPC_VERBOSITY=DEBUG
        #export GRPC_TRACE=api,call_combiner
        #export GRPC_TRACE=queue_pluck,flowctl,http1,http2_stream_state,http,op_failure
        #export GRPC_TRACE=client_channel,call_error,channel,server_channel,channel_stack_builder,connectivity_state  #all

        ##############
        # Arguments: #
        ##############
        # tf_command += " gdb --args"
        tf_command += " python -u %s/tf_cnn_benchmarks.py" % self._work_dir
        tf_command += " --job_name=%s" % job_name
        tf_command += " --task_index=%u" % task_id
        tf_command += " --worker_hosts=%s" % ",".join(self._cluster_workers)
        if self.mode() == TFCnnBenchmarksStep.MODE_PARAMETER_SERVER:
            tf_command += " --ps_hosts=%s" % ",".join(self._cluster_ps)
        elif self.mode() == TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE:
            tf_command += " --variable_update=distributed_all_reduce"
            tf_command += " --all_reduce_spec=%s" % self.all_reduce_spec()
        if job_name in ["worker", "controller"]:
            tf_command += " --model=%s" % self.model()
            tf_command += " --batch_size=%s" % self.batch_size()
            if self.data_dir() != "":
                tf_command += " --data_dir=%s" % self.data_dir()
            
            tf_command += " --data_dir=%s" % self.data_dir()
            if self.num_gpus() > 0:
                tf_command += " --num_gpus=%s --local_parameter_device=gpu" % self.num_gpus()
            if self.trace_file():
                tf_command += "--trace_file=trace_%s_%u.json" % (job_name, task_id)
        tf_command += " --server_protocol=%s" % self.server_protocol()        
        
        #command = " %s/run_job2.sh %s" % (self._work_dir, tf_command)
        command = tf_command

        title = "[%s] %s - %u" % (ip, job_name, task_id)
        log_file_path = os.path.join(self._logs_dir, "%s_%u.log" % (job_name, task_id))
        factory = BasicProcess.getFactory(title, log_file_path)
        process = executeRemoteCommand([server.hostname], command, factory = factory, verbose=False)[0]
        process.name = "%s_%u" % (job_name, task_id)
        process.job_name = job_name 
        process.task_id = task_id
        process.is_worker = job_name == "worker"
        process.rdma_device = device_info
        process.command = tf_command
        self._processes.append(process)
        server.processes.append(process)
        return process

    # -------------------------------------------------------------------- #
    
    def _onOut(self, line, process):
        if "RDMA device: " in line:
            process.rdma_device = line.split("RDMA device: ")[1]
        elif "RDMA port: " in line:
            process.rdma_port = int(line.split("RDMA port: ")[1])
        elif "Running warm up" in line:
            self._startServerMonitors(process.server)
        elif "images/sec" in line:
            if "total " in line:
                log(line, process)
                m = re.match("total images\/sec: ([0-9\.]+)", line)
                if m is None:
                    print "Error: Regex match failed. Please contact the developers to fix it."
                    print "Line: %s" % line
                    sys.exit(1)
                images_sec = float(m.group(1))
                process.perf.images_sec.val = images_sec
                process.perf.images_sec.total = images_sec
                process.perf.images_sec.min = images_sec
                process.perf.images_sec.max = images_sec
                process.perf.images_sec.count = 1
                self._stopServerMonitors(process.server)
            else:
                # https://regex101.com/
                m = re.match("([0-9]+)\s+images\/sec: ([0-9\.]+) \+\/- ([0-9\.]+) \(jitter = ([0-9\.]+)\)\s+([0-9\.]+)", line)
                if m is None:
                    print "Error: Regex match failed. Please contact the developers to fix it."
                    print "Line: %s" % line
                    sys.exit(1)
                    
                step = int(m.group(1))
                images_sec = float(m.group(2))
                deviation = float(m.group(3))
                jitter = float(m.group(4))
                loss = float(m.group(5))
#                 perf = process.monitor.get(["CPU.avg", "MEM.val", "RDTA.rate.avg", "RDTA.rate.max", "TDTA.rate.avg", "TDTA.rate.max"])
#                 gpu_perf = process.monitor.get(["%s.avg" % gpu for gpu in process.monitor.search("GPU")])
                process.perf.images_sec.update(images_sec)

                try:
                    cpu = 0#float(perf[0])
                    mem = 0#float(perf[1])
                    rx_rate_avg = 0#float(perf[2])
                    rx_rate_max = 0#float(perf[3])
                    tx_rate_avg = 0#float(perf[4])
                    tx_rate_max = 0#float(perf[5])
                    gpu = 0#sum([float(x) for x in gpu_perf]) / len(gpu_perf)
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
    
    def _onJobStart(self, process):
        handler = TestEnvironment.onNewProcess()
        if handler is not None:
            handler(process)
        title("Log: " + process.log_file_path, process = process) 
            
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
            if process.remote_pid and process.isAlive():
                log("   + [%s] %s: %u" % (process.server, process.name, process.instance.pid))
                os.kill(process.instance.pid, 15)            
                self.runInline("kill -15 %u >& /dev/null" % process.remote_pid, servers=[process.server], verbose=False)
        log("Done.")
         
    # -------------------------------------------------------------------- #

    def perform(self, index):
        Step.perform(self, index)
        log("<img src='images/tensorflow.jpg' width=600 style='border:1px solid black'/>") #https://www.skylinelabs.in/blog/images/tensorflow.jpg?width=500'/>")
        self._stopping = False
        work_dir_name = "tmp." + next(tempfile._get_candidate_names()) + next(tempfile._get_candidate_names())
        work_dir = os.path.join(tempfile._get_default_tempdir(), work_dir_name)
        script_dir = os.path.dirname(self._values[TFCnnBenchmarksStep.ATTRIBUTE_ID_SCRIPT])
        current_dir = os.path.dirname(os.path.realpath(__file__))
        
        user = getuser()
        self._work_dir = work_dir
        ips = list(set(self.ps() + self.workers()))
        servers = TestEnvironment.Get().getServers(ips)
            
        #########################
        # Kill other instances: #
        #########################
        kill_cmd = "ps -ef | grep tf_cnn_benchmarks.py | grep -v grep | grep %s | grep -v %s | sed -e 's@%s *\\([0-9]\\+\\) .*@\\1@g' | xargs kill -9" % (user, work_dir, user)
        res = self.runInline(kill_cmd, servers, wait_timeout = 5)
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
        if not self.runSCP(servers, [script_dir], work_dir, wait_timeout = 10): # Also create it
            return False
        if not self.runSCP(servers, [os.path.join(current_dir, "..", "Monitor.py"),
                                     os.path.join(current_dir, "..", "Common")], work_dir, wait_timeout = 10):
            return False
            
        ########
        # Run: #
        ########
        self._openPerformanceFile()
        self._getDevices(ips)
        
        title("Running:", UniBorder.BORDER_STYLE_SINGLE)
        processes = []
        if self.mode() == TFCnnBenchmarksStep.MODE_PARAMETER_SERVER:
            for i in range(len(self.ps())):
                ip = self.ps()[i]
                process = self._runJob(work_dir, ip, "ps", i)
                processes.append(process)
        elif self.mode() == TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE:
            process = self._runJob(work_dir, ip, "controller", 0)
            processes.append(process) 
        for i in range(len(self.workers())):
            ip = self.workers()[i]
            process = self._runJob(work_dir, ip, "worker", i)
            processes.append(process)
        
        self._findRemoteProcessIDs(processes)
        res = waitForProcesses(processes, 
                               wait_timeout=600,
                               on_output=self._onOut,
                               on_process_start=self._onJobStart,
                               on_process_done=self._onJobDone)
        if not res or self._stop:
            return False

        self._appendToPerformanceFile()
        
        ############
        # Cleanup: #
        ############
        title("Cleaning:", UniBorder.BORDER_STYLE_SINGLE)
        processes = executeRemoteCommand(ips, "rm -rf %s" % work_dir)
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

