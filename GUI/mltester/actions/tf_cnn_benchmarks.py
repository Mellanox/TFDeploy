#!/usr/bin/python
# -*- coding: utf-8 -*-

from getpass import getuser
import tempfile
import sys
import re
import os
import time
import threading

from mltester.actions import Step, DefaultAttributesWidget, TestEnvironment
from commonpylib.log import ScreenLogWriter, FileLogWriter, LOG_LEVEL_NOTE, \
    log, note, debug, title, error, warning, FormattedTable, UniBorder
from commonpylib.monitors import Measurement, RemoteMonitor
from commonpylib.util import BasicProcess, executeRemoteCommand, waitForProcesses, toFileName, ListAttribute, \
                             IntAttribute, PathAttribute, StrAttribute, BoolAttribute, tryExp, _res

###############################################################################

class ServerInfo(object):
    def __init__(self, ip, hostname):
        self.ip = ip
        self.hostname = hostname
        self.processes = []
        self.monitor = None
        self.monitor_lock = threading.Lock()

###############################################################################

class RemoteDeviceInfo(object):
    def __init__(self):
        self.net_name = None
        self.name = None
        self.port = 0
        self.is_up = False

###############################################################################

class TFPerformanceMeasurements(object):
    def __init__(self, process = None):
        self.images_sec = Measurement("IMG/SEC")
        self.gpu = Measurement("GPU", "%")
        if process:
            remote_dev = "%s:%u" % (process.rdma_device.name, process.rdma_device.port)
            self.stime                           = Measurement("STIME-%u" % process.remote_pid)
            self.utime                           = Measurement("UTIME-%u" % process.remote_pid)
            self.rx                              = Measurement("RDTA-%s" % remote_dev, "Mbit", True)
            self.tx                              = Measurement("TDTA-%s" % remote_dev, "Mbit", True)
            self.excessive_buffer_overrun_errors = Measurement("XBUF_OVERRUN_ERRORS-%s" % remote_dev)
            self.port_xmit_discards              = Measurement("PORT_XMIT_DISCARDS-%s" % remote_dev)
            self.port_xmit_waits                 = Measurement("PORT_XMIT_WAITS-%s" % remote_dev)
            self.port_rcv_errors                 = Measurement("PORT_RCV_ERRORS-%s" % remote_dev)
            self.port_rcv_constraint_errors      = Measurement("PORT_RCV_CONSTRAINT_ERRORS-%s" % remote_dev)
        else:
            self.stime                           = Measurement("STIME")
            self.utime                           = Measurement("UTIME")
            self.rx                              = Measurement("RDTA", "Mbit", True)
            self.tx                              = Measurement("TDTA", "Mbit", True)
            self.excessive_buffer_overrun_errors = Measurement("XBUF_OVERRUN_ERRORS")
            self.port_xmit_discards              = Measurement("PORT_XMIT_DISCARDS")
            self.port_xmit_waits                 = Measurement("PORT_XMIT_WAITS")
            self.port_rcv_errors                 = Measurement("PORT_RCV_ERRORS")
            self.port_rcv_constraint_errors      = Measurement("PORT_RCV_CONSTRAINT_ERRORS")
    
    # -------------------------------------------------------------------- #
    
    def reduce(self, other):
        self.images_sec.reduce(other.images_sec)
        self.gpu.reduce(other.gpu)
        self.stime.val += other.stime.val
        self.utime.val += other.utime.val
        self.rx.reduce(other.rx)
        self.tx.reduce(other.tx)
        self.excessive_buffer_overrun_errors.reduce(other.excessive_buffer_overrun_errors)
        self.port_xmit_discards.reduce(other.port_xmit_discards)
        self.port_xmit_waits.reduce(other.port_xmit_waits)
        self.port_rcv_errors.reduce(other.port_rcv_errors)
        self.port_rcv_constraint_errors.reduce(other.port_rcv_constraint_errors)

###############################################################################

@Step.REGISTER()
class TFCnnBenchmarksStep(Step):
    
    NAME = "TF CNN Benchmarks"
    
    VARIABLE_UPDATE_MODES = ["parameter_server", "replicated", "distributed_replicated",
                             "independent", "distributed_all_reduce",
                             "collective_all_reduce", "horovod", "local"]
    ALL_REDUCE_SPECS = ["xring", "xring#2", "nccl", "nccl/xring", "pscpu", "psgpu#4", "pscpu:2k:pscpu#2:64k:xring", "pscpu/pscpu#2"] 
    MODELS = ["trivial", "inception3", "inception4", "resnet50", "resnet101", "resnet152", "vgg16", "vgg19"]
    PROTOCOLS = ["grpc", "grpc+verbs", "grpc+ucx", "grpc+mpi"]
    OPERATION_MODES = ["Training", "Inception"]
    
    ATTRIBUTE_ID_MODE = 0
    ATTRIBUTE_ID_ALL_REDUCE_SPECS = 1
    ATTRIBUTE_ID_CONTROLLER = 2
    ATTRIBUTE_ID_PS = 3
    ATTRIBUTE_ID_WORKERS = 4
    ATTRIBUTE_ID_SERVER_PROTOCOL = 9
    
    ATTRIBUTES = [StrAttribute ("variable_update" , "Variable Update", VARIABLE_UPDATE_MODES[0], VARIABLE_UPDATE_MODES),
                  StrAttribute ("all_reduce_spec" , "All-Reduce Spec", ALL_REDUCE_SPECS[0], ALL_REDUCE_SPECS),
                  StrAttribute ("controller"      , "Controller", "12.12.12.25"),
                  ListAttribute("ps"              , "PS", "12.12.12.25"),
                  ListAttribute("workers"         , "Workers", "12.12.12.25,12.12.12.26"),
                  PathAttribute("script"          , "Script", os.path.join(tryExp(["$TF_BENCHMARKS_HOME", "~/benchmarks"]), "scripts", "tf_cnn_benchmarks", "tf_cnn_benchmarks.py")),
                  StrAttribute ("model"           , "Model", "vgg16", MODELS),
                  IntAttribute ("batch_size"      , "Batch Size", "32"),
                  IntAttribute ("num_gpus"        , "Num GPUs", "2"),
                  StrAttribute ("server_protocol" , "Server Protocol", "grpc+verbs", PROTOCOLS),
                  PathAttribute("data_dir"        , "Data Dir", "/data/imagenet_data/"),
                  IntAttribute ("base_port"       , "Base Port", "5000", category="Advanced"),
                  IntAttribute ("log_level"       , "Log Level", "0", category="Advanced"),
                  BoolAttribute("trace_file"      , "Trace File", "False", category="Advanced"),
                  BoolAttribute("model_graph_file", "Graph File", "False", category="Advanced"),
                  BoolAttribute("forward_only"    , "Forward Only", "False", category="Advanced"),
                  BoolAttribute("use_ibprof"      , "Use ibprof", "False", category="Advanced"),
                  BoolAttribute("use_nvprof"      , "Use nvprof", "False", category="Advanced"),
                  BoolAttribute("use_gdb"         , "Use gdb", "False", category="Advanced")]

    # -------------------------------------------------------------------- #

    class AttributesWidget(DefaultAttributesWidget):
        def __init__(self, attributes, parent = None):
            super(TFCnnBenchmarksStep.AttributesWidget, self).__init__(attributes, parent = None)
            self._refreshFields()
        
        # ---------------------------------------- #
        
        def _refreshFields(self):
            is_local                 = self._attributes.variable_update == "local"
            is_ps                    = self._attributes.variable_update == "parameter_server"
            is_replicated            = self._attributes.variable_update == "replicated"
            is_dist_replicated       = self._attributes.variable_update == "distributed_replicated"
            #is_independent           = self._attributes.variable_update == "independent"
            is_dist_all_reduce       = self._attributes.variable_update == "distributed_all_reduce"
            is_collective_all_reduce = self._attributes.variable_update == "collective_all_reduce"
            is_horovod               = self._attributes.variable_update == "horovod"
            
            uses_ps                  = is_ps or is_dist_replicated
            uses_all_reduce          = is_replicated or is_dist_replicated or is_dist_all_reduce or is_collective_all_reduce
            
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_ALL_REDUCE_SPECS, uses_all_reduce)
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_CONTROLLER, is_dist_all_reduce)
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_PS, uses_ps)
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_SERVER_PROTOCOL, not is_local and not is_horovod)
        
        # ---------------------------------------- #
            
        def _onFieldChanged(self, field_index, val):
            DefaultAttributesWidget._onFieldChanged(self, field_index, val)
            self._refreshFields()
       
        # ---------------------------------------- #
        
        def load(self, values):
            DefaultAttributesWidget.load(self, values)
            self._refreshFields()
    
    # -------------------------------------------------------------------- #
    
    WIDGET_CLASS = AttributesWidget

    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        Step.__init__(self, values)
    
    # -------------------------------------------------------------------- #
    
    def is_local(self):
        return self._attributes.variable_update == "local"
    def is_ps(self):
        return self._attributes.variable_update == "parameter_server"
    def is_replicated(self):
        return self._attributes.variable_update == "replicated"
    def is_dist_replicated(self):
        return self._attributes.variable_update == "distributed_replicated"
    def is_independent(self):
        return self._attributes.variable_update == "independent"
    def is_dist_all_reduce(self):
        return self._attributes.variable_update == "distributed_all_reduce"
    def is_collective_all_reduce(self):
        return self._attributes.variable_update == "collective_all_reduce"
    def is_horovod(self):
        return self._attributes.variable_update == "horovod"
    def is_cluster_run(self):
        return not self.is_local() and not self.is_horovod()
    def uses_ps(self):
        return self.is_ps() or self.is_dist_replicated()
    def uses_controller(self):
        return self.is_dist_all_reduce()
    def uses_all_reduce(self):
        return self.is_dist_all_reduce() or self.is_collective_all_reduce() or self.is_replicated() or self.is_dist_replicated()
    def hostnames(self):
        return self._servers.keys() 
    
    # -------------------------------------------------------------------- #
    
    def attributesRepr(self):
        if self.is_local():
            return "%s, LOCAL, %u GPU, batch %u" % (self.model,
                                                    self.num_gpus,
                                                    self.batch_size)
        else:
            return "%s, %s, %u GPUs, batch %u" % (self.model,
                                                  self.server_protocol,
                                                  self.num_gpus * len(self.workers),
                                                  self.batch_size) 
    
    # -------------------------------------------------------------------- #
    
    def _logTable(self, table):
        table.printHTML(ScreenLogWriter(None, log_level=LOG_LEVEL_NOTE))
        table.printFormatted(FileLogWriter(None, log_level=LOG_LEVEL_NOTE))
    
    # -------------------------------------------------------------------- #
    
    def _killPreviousRuns(self):
        apps_to_kill = ["tf_cnn_benchmarks.py", "ml_monitor", "nvidia-smi"]
        for app in apps_to_kill:
            kill_cmd = "ps -f | grep %s | grep -v grep | grep -v %s | sed -e 's@%s *\\([0-9]\\+\\) .*@\\1@g' | xargs kill -9" % (app, self._work_dir, self._user)
            if not self.runInline(kill_cmd, servers=self.hostnames(), wait_timeout=5):
                return False
        return True
    
    # -------------------------------------------------------------------- #
    
    def _copyScripts(self):
        return self.runSCP([self._script_dir], self._work_dir, dst_servers=self.hostnames(), wait_timeout=10) # Also create it
    
    # -------------------------------------------------------------------- #
    
    def _appendToPerformanceFile(self):
        ''' Overall step performance (average all workers). '''
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
        self._performance_table.addColumn(FormattedTable.Column("CPU time", 9), "Performance")
        self._performance_table.addColumn(FormattedTable.Column("MEM%", 5), "Performance")
        self._performance_table.addColumn(FormattedTable.Column("GPU%", 5), "Performance")
        self._performance_table.addColumn(FormattedTable.Column("Average", 18), "RX/TX rate (Mbit/sec)")
        self._performance_table.addColumn(FormattedTable.Column("Max", 18), "RX/TX rate (Mbit/sec)")
        self._performance_table.addColumn(FormattedTable.Column("Buffer overrun"), "Network Errors")
        self._performance_table.addColumn(FormattedTable.Column("TX discards"), "Network Errors")
        self._performance_table.addColumn(FormattedTable.Column("TX waits"), "Network Errors")
        self._performance_table.addColumn(FormattedTable.Column("RX errors"), "Network Errors")
        self._performance_table.addColumn(FormattedTable.Column("RX constraint errors"), "Network Errors")
        self._performance_table.bind([FormattedTable.CsvStream(self._performance_file, print_header = first_time)])
        
        for process in self._jobs:
            if process.perf is not None:
                # Append to global performance results:
                self._perf.reduce(process.perf)
        
        log("Appending to results file: <a href=\"%s\">%s</a>" % (self._performance_file.name, self._performance_file.name)) 
        row = [time.strftime("%Y-%m-%d %H:%M:%S"),
               "TF cnn benchmarks",
               self.model,
               self.batch_size,
               self.server_protocol,
               self.num_gpus,
               len(self.workers),
               len(self.ps),
               "%.2lf" % self._perf.images_sec.avg,
               "%.2lf" % (self._perf.utime.val + self._perf.stime.val),
               "%.2lf" % 0.0,
               "%.2lf" % self._perf.gpu.avg,
               "%.2lf/%.2lf" % (self._perf.rx.rate.avg, self._perf.tx.rate.avg),
               "%.2lf/%.2lf" % (self._perf.rx.rate.max, self._perf.tx.rate.max),
               self._perf.excessive_buffer_overrun_errors.val,
               self._perf.port_xmit_discards.val,
               self._perf.port_xmit_waits.val,
               self._perf.port_rcv_errors.val,
               self._perf.port_rcv_constraint_errors.val]
        self._performance_table.addRow(row)
        self._performance_table.unbind()
        self._performance_file.close()
        
        summary_table = self._performance_table.cut(["Performance", "RX/TX rate (Mbit/sec)", "Network Errors"])
        self._logTable(summary_table)
    
    # -------------------------------------------------------------------- #
    
    def _getOrCreateServer(self, hostname, ip):
        if hostname in self._servers:
            return self._servers[hostname]
        server = ServerInfo(ip, hostname)
        self._servers[hostname] = server
        return server

    # -------------------------------------------------------------------- #
    
    def _initServerMonitors(self, server_info):
        server_info.graphs_dir = os.path.join(self._logs_dir, "graphs", toFileName(server_info.hostname))
        server_info.remote_graphs_dir = os.path.join(self._work_dir, "graphs")
        if not os.path.exists(server_info.graphs_dir):
            os.makedirs(server_info.graphs_dir)
        remote_monitor_title = lambda process: "Monitor [%s]" % process.server
        remote_monitor_bin = "ml_monitor"
        
        monitored_pids = ",".join(["%u" % p.remote_pid for p in server_info.processes])
        monitored_nics = ",".join(["%s:%u" % (p.rdma_device.name, p.rdma_device.port) for p in server_info.processes])
        remote_monitor_flags = "--cpu %s 0.010 --gpu 0.020 --net %s 0.010 --net_errors %s 1 -d %s" % (monitored_pids, 
                                                                                                      monitored_nics,
                                                                                                      monitored_nics,
                                                                                                      server_info.remote_graphs_dir)
        server_info.monitor_log_path = os.path.join(server_info.graphs_dir, "monitor.log") 
        server_info.monitor = RemoteMonitor(server_info.hostname, remote_monitor_bin, remote_monitor_flags, remote_monitor_title, server_info.monitor_log_path)
        return True

    # -------------------------------------------------------------------- #
    
    def _startServerMonitors(self, hostname):
        server_info = self._servers[hostname]
        if server_info.monitor is None:
            return True
        
        log("Server %s: Starting monitor." % server_info.ip)
        return server_info.monitor.start()
    
    # -------------------------------------------------------------------- #
    
    def _stopServerMonitors(self, server_info):
        if server_info.monitor is None:
            return True
        
        log("Server %s: Stopping monitor." % server_info.ip)
        res = server_info.monitor.stop()
        server_info.monitor.close()
        sources = ["%s/*" % server_info.remote_graphs_dir]
        self.runSCP(sources, server_info.graphs_dir, src_servers=[server_info.hostname])
        server_info.monitor = None
        return res
    
    # -------------------------------------------------------------------- #
    
    def _stopAllMonitors(self):
        for server_info in self._servers.values():
            self._stopServerMonitors(server_info)
    
    # -------------------------------------------------------------------- #
    
    def _initProcessReport(self, process):
        process.perf = TFPerformanceMeasurements(process)
        process.perf.images_sec = Measurement("IMG/SEC")
        process.table = FormattedTable()
        process.table.addColumn(FormattedTable.Column("STEP", 4))
        process.table.addColumn(FormattedTable.Column("CPU time", 9))
        process.table.addColumn(FormattedTable.Column("MEM%", 5))
        process.table.addColumn(FormattedTable.Column("GPU%", 5))
        process.table.addColumn(FormattedTable.Column("RX/TX (MBit/sec)", 12))
        process.table.addColumn(FormattedTable.Column("Max RX/TX (MBit/sec)", 12))
        process.table.addColumn(FormattedTable.Column("images/sec", 12))
        process.table.addColumn(FormattedTable.Column("+/-", 7))
        process.table.addColumn(FormattedTable.Column("jitter", 6))
        process.table.addColumn(FormattedTable.Column("loss", 6))
        process.table.bind([FormattedTable.UniborderStream(ScreenLogWriter(process, log_level=LOG_LEVEL_NOTE), style=UniBorder.BORDER_STYLE_STRONG),
                            FormattedTable.UniborderStream(FileLogWriter(process, log_level=LOG_LEVEL_NOTE), style=UniBorder.BORDER_STYLE_STRONG)])
    
    # -------------------------------------------------------------------- #
    
    def _finishProcessReport(self, process):
        if process.server_info.monitor is not None:
            process.server_info.monitor.fillMeasurement(process.perf.stime)
            process.server_info.monitor.fillMeasurement(process.perf.utime)
            process.server_info.monitor.fillMeasurement(process.perf.rx)
            process.server_info.monitor.fillMeasurement(process.perf.tx)
            process.server_info.monitor.fillMeasurement(process.perf.excessive_buffer_overrun_errors)
            process.server_info.monitor.fillMeasurement(process.perf.port_xmit_discards)
            process.server_info.monitor.fillMeasurement(process.perf.port_xmit_waits)
            process.server_info.monitor.fillMeasurement(process.perf.port_rcv_errors)
            process.server_info.monitor.fillMeasurement(process.perf.port_rcv_constraint_errors)
            for gpu_id in process.server_info.monitor.search("GPU"):
                gpu = Measurement(gpu_id)
                process.server_info.monitor.fillMeasurement(gpu)
                process.perf.gpu.reduce(gpu)
        
        row = ["---",
               "%.2lf" % (process.perf.utime.val + process.perf.stime.val),
               "%.2lf" % 0.0, 
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
        process.processes = []

    # -------------------------------------------------------------------- #
    
    def _findRemoteProcessIDs(self):
        remote_process_ids = {}
        def parser(line, find_process):
            debug(line)
            key = find_process.name
            remote_process_ids[key] = int(line.split()[0])
       
        res = True
        num_attempts = 0
        max_num_attempts = 3
        while len(remote_process_ids) < len(self._jobs):
            find_processes = []
            for process in self._jobs:
                if process.name in remote_process_ids:
                    continue
                find_process = executeRemoteCommand([process.server],  "ps --no-headers -o\"pid,args\" | grep -e '^ *[0-9]\+ %s$'" % process.tf_command)[0]
                find_process.name = process.name
                find_processes.append(find_process)
                
            waitForProcesses(find_processes, wait_timeout=5, on_output=parser)
            time.sleep(0.5)
            num_attempts += 1
            if num_attempts == max_num_attempts:
                error("Failed to find remote process IDs. Most likely some processes failed to run.")
                res = False
                break
            
        for process in self._jobs:
            if process.name in remote_process_ids:
                process.remote_pid = remote_process_ids[process.name]
        return res
    
    # -------------------------------------------------------------------- #
    
    def _printProcessSummary(self):
        table = FormattedTable()
        table.addColumn(FormattedTable.Column("IP"))
        table.addColumn(FormattedTable.Column("Job"))
        table.addColumn(FormattedTable.Column("PID"))
        table.addColumn(FormattedTable.Column("RPID"))
        table.addColumn(FormattedTable.Column("Flags"))
        table.addColumn(FormattedTable.Column("Command"))
        for process in self._jobs:
            table.addRow([process.server_info.ip,
                          "<a href=\"%s\">%s</a>" % (process.log_file_path, process.name),
                          process.instance.pid, process.remote_pid, process.tf_flags, process.tf_command])
        self._logTable(table)
    
    # -------------------------------------------------------------------- #
            
    def _getDevices(self, ips):
        def netNameParser(line, process):
            debug(line, process)
            device = RemoteDeviceInfo()
            device.net_name = line
            self._devices[process.server] = device
        
        def deviceNameAndPortParser(line, process):
            debug(line, process)
            parts = line.split()
            device = self._devices.get(process.server)
            device.name = parts[0]
            device.port = int(parts[2])
            device.is_up = parts[5] == "(Up)"
        
        procs = []
        for ip in ips:
            hostname = TestEnvironment.Get().getHostname(ip)
            procs.extend(executeRemoteCommand([hostname], "ip -o a s | grep %s | cut -d ' ' -f 2 | cut -d'.' -f1" % ip))
        if not waitForProcesses(procs, wait_timeout=5, on_output=netNameParser):
            for proc in procs:
                if proc.exception is not None:
                    raise proc.exception
            raise Exception("Internal Error")
        
        procs = []
        for ip in ips:
            hostname = TestEnvironment.Get().getHostname(ip)
            device = self._devices.get(hostname)
            if not device:
                error("IP %s: No device found." % ip)
                continue
            procs.extend(executeRemoteCommand([hostname], "ibdev2netdev | grep %s" % device.net_name))
        
        if len(procs) < len(ips):
            return False
            
        if not waitForProcesses(procs, wait_timeout=5, on_output=deviceNameAndPortParser):
            for proc in procs:
                if proc.exception is not None:
                    raise proc.exception
            raise Exception("Internal Error")
        return True

    # -------------------------------------------------------------------- #
    
    def _buildCluster(self):
        ips = self._getIPs()
        for ip in ips:
            hostname = TestEnvironment.Get().getHostname(ip)
            self._getOrCreateServer(hostname, ip)
        
        if not self._getDevices(ips) or self._stop:
            return False
        
        port = self.base_port
        self._cluster_ps = []
        self._cluster_workers = []
        self._cluster_servers = []
        for ip in self.ps:
            self._cluster_ps.append("%s:%u" % (ip, port))
            port += 1
        for ip in self.workers:
            self._cluster_workers.append("%s:%u" % (ip, port))
            port += 1
        
        self._cluster_ps = ",".join(self._cluster_ps)
        self._cluster_workers = ",".join(self._cluster_workers)
        
        table = FormattedTable()
        table.addColumn(FormattedTable.Column("IP"))
        table.addColumn(FormattedTable.Column("Host"))
        table.addColumn(FormattedTable.Column("Device"))
        table.addColumn(FormattedTable.Column("Port"))
        table.addColumn(FormattedTable.Column("Net Name"))
        table.addColumn(FormattedTable.Column("Status"))
        for ip in ips:
            hostname = TestEnvironment.Get().getHostname(ip)
            device_info = self._devices[hostname]
            table.addRow([ip, hostname, device_info.name, device_info.port, device_info.net_name, "Up" if device_info.is_up else "Down"])
        self._logTable(table)
        return True
    
    # -------------------------------------------------------------------- #
    
    def _createJob(self, ip, job_name, task_id):
        hostname = TestEnvironment.Get().getHostname(ip)
        server_info = self._getOrCreateServer(hostname, ip)
        device_info = self._devices[server_info.hostname]
        
        #####################
        # Build TF command: #
        #####################
        tf_flags = ""
        tf_command =  ""
        
        ##################
        # Env variables: #
        ##################
        cuda_lib_dir    = "/usr/local/cuda/lib64"
        gdrcopy_lib_dir = "/usr/local/gdrcopy"
        mpi_lib_dir     = "/machineLearning/installs/openmpi-3.1.0/install/lib/"
        cuda_extra_dir  = "/usr/local/cuda/extras/CUPTI/lib64"
        tf_flags += "LD_LIBRARY_PATH=$LD_LIBRARY_PATH:%s:%s:%s" % (cuda_lib_dir, gdrcopy_lib_dir, mpi_lib_dir)
        if self.trace_file:
            tf_flags += ":%s" % (cuda_extra_dir)

        tf_flags += " TF_CPP_MIN_VLOG_LEVEL=%s" % self.log_level
        if (job_name in ["ps", "controller"]) or (self.num_gpus == 0):
            tf_flags += " CUDA_VISIBLE_DEVICES="
            
        if self.use_ibprof:
            tf_flags += " LD_PRELOAD=/opt/mellanox/libibprof/lib/libibprof.so"

        ################
        # Verbs stuff: #
        ################
        if self.server_protocol == "grpc+verbs":
            tf_flags += " RDMA_DEVICE=%s" % device_info.name
            tf_flags += " RDMA_DEVICE_PORT=%u" % device_info.port
            tf_flags += " RDMA_GID_INDEX=3"
            tf_flags += " RDMA_PKEY=0"
            tf_flags += " RDMA_QUEUE_DEPTH=1024"
            tf_flags += " RDMA_TIMEOUT=10"
            tf_flags += " RDMA_RETRY_CNT=10"
            tf_flags += " RDMA_SL=1"
            tf_flags += " RDMA_MTU=512"
            tf_flags += " RDMA_TRAFFIC_CLASS=8"

        ##############  
        # UCX stuff: #
        ##############
        # Ucx should be compiled ./contrib/configure-devel --enable-debug
        if self.server_protocol == "grpc+ucx":
            tf_flags += " UCX_LOG_LEVEL=data"
            tf_flags += " UCX_TLS=rc_x,gdr_copy,cuda_copy"
            tf_flags += " UCX_NET_DEVICES=%s:%u" % (device_info.name, device_info.port)
        #export UCX_IB_ETH_PAUSE_ON=y
        #export UCX_LOG_LEVEL=trace 

        ##############
        # MPI stuff: #
        ##############
        if self.server_protocol == "grpc+mpi":
            pass
        
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
        if self.use_gdb:
            tf_command += " gdb --args"
        elif self.use_nvprof:
            if (job_name == "worker") and (task_id == 0):
                tf_command += " nvprof -f -o /tmp/worker_0.nvvp -- "
        
        if self.is_horovod():
            if task_id == 0: 
                tf_command += "mpirun -H %s" % ",".join(["%s:%u" % (TestEnvironment.Get().getServer(wip), self.num_gpus) for wip in self.workers])
                tf_command += " -bind-to none -map-by slot"
                tf_command += " -x NCCL_DEBUG=INFO -x LD_LIBRARY_PATH -x PATH"
                tf_command += " -mca pml ob1 -mca btl ^openib -- "
            else:
                return None
        tf_command += "python -u %s/tf_cnn_benchmarks.py" % self._work_dir
        
        if not self.is_local():
            tf_command += " --variable_update=%s" % self.variable_update

        if self.is_cluster_run():
            tf_command += " --job_name=%s" % job_name
            tf_command += " --task_index=%u" % task_id
            tf_command += " --worker_hosts=%s" % self._cluster_workers
        
        if self.uses_ps():
            tf_command += " --ps_hosts=%s" % self._cluster_ps
            
        if self.uses_all_reduce():
            tf_command += " --all_reduce_spec=%s" % self.all_reduce_spec
        
        if job_name in ["worker", "controller"]:
            tf_command += " --model=%s" % self.model
            tf_command += " --batch_size=%s" % self.batch_size
            if self.data_dir != "":
                tf_command += " --data_dir=%s" % self.data_dir
            if (self.num_gpus > 0) and not self.is_horovod():
                tf_command += " --num_gpus=%s" % self.num_gpus
            if self.trace_file:
                tf_command += " --trace_file=%s" % os.path.join(self._work_dir, "trace_%s_%u.json" % (job_name, task_id))
        
        if self.is_cluster_run():
            tf_command += " --server_protocol=%s" % self.server_protocol
        
        if self.forward_only:
            tf_command += " --forward_only"
        
        if self.model_graph_file and (task_id == 0):
            tf_command += " --graph_file=%s" % os.path.join(self._work_dir, "graph.txt")
        
        command = tf_flags + " " + tf_command
        
        title = "[%s] %s - %u" % (server_info.ip, job_name, task_id)
        log_file_path = os.path.join(self._logs_dir, "%s_%u.log" % (job_name, task_id))
        factory = BasicProcess.getFactory(title, log_file_path)
        process = executeRemoteCommand([server_info.hostname], command, factory = factory)[0]
        process.name = "%s_%u" % (job_name, task_id)
        process.job_name = job_name 
        process.task_id = task_id
        process.is_worker = job_name == "worker"
        process.is_ps = job_name == "ps"
        process.is_controller = job_name == "controller"
        process.rdma_device = device_info
        process.server_info = server_info
        process.tf_flags = tf_flags
        process.tf_command = tf_command
        process.remote_pid = None
        process.perf = None
        self._jobs.append(process)
        server_info.processes.append(process)
    
    # -------------------------------------------------------------------- #
    
    def _onOut(self, line, process):
        if "Running warm up" in line or "Starting worker " in line:
            log(line, process)
            self._initProcessReport(process)
            if not self._startServerMonitors(process.server):
                warning("Warning: Failed to start monitor for server %s.\n" % process.server)
                process.server_info.monitor = None 
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
                self._finishProcessReport(process)
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
                if process.server_info.monitor is not None:
                    remote_dev = "%s:%u" % (process.rdma_device.name, process.rdma_device.port)
                    perf = process.server_info.monitor.get(["UTIME-%u.val" % process.remote_pid,
                                                            "STIME-%u.val" % process.remote_pid,
                                                            "RDTA-%s.rate.avg" % remote_dev,
                                                            "RDTA-%s.rate.max" % remote_dev,
                                                            "TDTA-%s.rate.avg" % remote_dev, 
                                                            "TDTA-%s.rate.max" % remote_dev])
                    gpu_perf = process.server_info.monitor.get(["%s.avg" % gpu for gpu in process.server_info.monitor.search("GPU")])
                    #cpu_perf = process.server_info.monitor.get(["%s.avg" % gpu for gpu in process.server_info.monitor.search("GPU")])
                else:
                    perf = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                    gpu_perf = [0.0]
                process.perf.images_sec.update(images_sec)

                try:
                    cpu = float(perf[0]) + float(perf[1])
                    mem = 0.0
                    rx_rate_avg = float(perf[2])
                    rx_rate_max = float(perf[3])
                    tx_rate_avg = float(perf[4])
                    tx_rate_max = float(perf[5])
                    gpu = sum([float(x) for x in gpu_perf]) / len(gpu_perf)
                except:
                    error("Server %s: Remote monitor process failed. See %s for more info." % (process.server_info.ip, process.server_info.monitor_log_path))
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
        handler = TestEnvironment.Get().on_new_process
        if handler is not None:
            handler(process)
        note("Log: %s" % process.log_file_path, process = process) 
    
    # -------------------------------------------------------------------- #
    
    def _onJobDone(self, process):
        handler = TestEnvironment.Get().on_process_done
        if handler is not None:
            handler(process)
        
        res = process.instance.returncode in [0, 143, -15]
        if res:
            log("[%s]: Process %s finished successfully." % (process.server_info.ip, process.name))
            if self.uses_ps():
                if process.is_worker:
                    self._num_finished_workers += 1
                    if self._num_finished_workers == len(self.workers):
                        log("All workers are done. Stopping ps processes.")
                        self._stopExternalProcesses(self._jobs)
            elif self.uses_controller():
                if process.is_controller:
                    log("Controller is done. Stopping worker processes.")
                    self._stopExternalProcesses(self._jobs)
        else:
            error("[%s]: Process %s failed." % (process.server_info.ip, process.name))
        return res
    
    # -------------------------------------------------------------------- #
    
    def _getIPs(self):
        if self.is_local():
            res = [self.workers[0]]
        elif self.uses_ps():
            res = list(set(self.ps + self.workers))
        elif self.is_dist_all_reduce():
            res = list(set([self.controller] + self.workers))
        else:
            res = list(set(self.workers))
        return sorted(res)
    
    # -------------------------------------------------------------------- #
    
    def _runJobs(self):
        if self.uses_ps():
            for i in range(len(self.ps)):
                ip = self.ps[i]
                self._createJob(ip, "ps", i)
        
        if self.is_dist_all_reduce():
            ip = self.controller
            self._createJob(ip, "controller", 0)
        
        worker_ips = [self.workers[0]] if self.is_local() else self.workers
        for i in range(len(worker_ips)):
            ip = self.workers[i]
            self._createJob(ip, "worker", i)
        
        time.sleep(0.2)
        res = self._findRemoteProcessIDs()
        self._printProcessSummary()
        if res:
            if not self.is_horovod():
                for server in self._servers.values():
                    if not self._initServerMonitors(server):
                        return False
        return res
    
    # -------------------------------------------------------------------- #
    
    def _waitForJobs(self):
        return waitForProcesses(self._jobs, 
                                wait_timeout=1800,
                                on_output=self._onOut,
                                on_process_start=self._onJobStart,
                                on_process_done=self._onJobDone)
    
    # -------------------------------------------------------------------- #
    
    def _copyResults(self):
        if len(self._jobs) == 0:
            return
        sources = ["%s/graph.txt" % self._work_dir, 
                   "%s/*.json" % self._work_dir]
        self.runSCP(sources, self._logs_dir, src_servers=self._servers.keys(), wait_timeout=20)
    
    # -------------------------------------------------------------------- #
    
    def _cleanup(self):
        title("Cleaning:", style = 2)
        self._stopAllMonitors()
        self._copyResults()
    
    # -------------------------------------------------------------------- #
    
    def _stepFailed(self):
        self._cleanup()
        return False
    
    # -------------------------------------------------------------------- #
    
    def _perform(self):
        log("<br><img src='%s' width=600 style='border:1px solid black'/><br>" % _res("images/tensorflow.jpg")) #https://www.skylinelabs.in/blog/images/tensorflow.jpg?width=500'/>")
        for attr in self._attributes:
            log(" + %s: %s" % (attr.desc.display_name, str(attr.val)))
        self._perf = TFPerformanceMeasurements()
        self._num_finished_workers = 0
        self._jobs = [] 
        self._servers = {}
        self._devices = {}
        work_dir_name = "tmp." + next(tempfile._get_candidate_names()) + next(tempfile._get_candidate_names())
        self._work_dir = os.path.join(tempfile._get_default_tempdir(), work_dir_name)
        self._script_dir = os.path.dirname(self.script)
        self._user = getuser()
        
        title("Building cluster:", style = 2)
        if not self._buildCluster() or self._stop:
            return False
        
        title("Killing previous runs:", style = 2)
        if not self._killPreviousRuns() or self._stop:
            return False
        
        title("Copying scripts:", style = 2)
        if not self._copyScripts() or self._stop:
            return False
        
        title("Running:", style = 2)
        if not self._runJobs() or self._stop:
            return False
        
        title("Waiting for processes to end:", style = 2)
        if not self._waitForJobs() or self._stop:
            return False
        
        self._appendToPerformanceFile()
        return True
    
    # -------------------------------------------------------------------- #
    
    def perform(self, index):
        Step.perform(self, index)
        res = self._perform()
        self._cleanup()
        return res
    
    # -------------------------------------------------------------------- #
    
    def _stopAction(self):
        self._stopExternalProcesses(self._jobs)
