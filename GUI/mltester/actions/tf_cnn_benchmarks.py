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
from commonpylib.log import LogWriter, LOG_LEVEL_NOTE, LOG_LEVEL_INFO, log, note, debug, title, error, warning, UniBorder, FormattedTable
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
        self.link = None
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
            self.port_rcv_errors                 = Measurement("PORT_RCV_ERRORS-%s" % remote_dev)
            self.port_rcv_constraint_errors      = Measurement("PORT_RCV_CONSTRAINT_ERRORS-%s" % remote_dev)
        else:
            self.stime                           = Measurement("STIME")
            self.utime                           = Measurement("UTIME")
            self.rx                              = Measurement("RDTA", "Mbit", True)
            self.tx                              = Measurement("TDTA", "Mbit", True)
            self.excessive_buffer_overrun_errors = Measurement("XBUF_OVERRUN_ERRORS")
            self.port_xmit_discards              = Measurement("PORT_XMIT_DISCARDS")
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
        self.port_rcv_errors.reduce(other.port_rcv_errors)
        self.port_rcv_constraint_errors.reduce(other.port_rcv_constraint_errors)
        
###############################################################################

@Step.REGISTER()
class TFCnnBenchmarksStep(Step):
    
    NAME = "TF CNN Benchmarks"
    
    MODE_PARAMETER_SERVER = 0
    MODE_DISTRIBUTED_ALL_REDUCE = 1
    MODE_HOROVOD = 2
    MODE_LOCAL = 3
    
    MODE_NAMES = ["Parameter Server", "Distributed All-Reduce", "Horovod", "Local"]
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
    
    ATTRIBUTES = [EnumAttribute("mode"            , "Mode", MODE_NAMES[0], MODE_NAMES),
                  StrAttribute ("all_reduce_spec" , "All-Reduce Spec", ALL_REDUCE_SPECS[0], ALL_REDUCE_SPECS),
                  ListAttribute("controller"      , "Controller", "12.12.12.25"),
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
                  BoolAttribute("use_ibprof"      , "Use IBprof", "False", category="Advanced")]

    # -------------------------------------------------------------------- #

    class AttributesWidget(DefaultAttributesWidget):
        def __init__(self, attributes, parent = None):
            super(TFCnnBenchmarksStep.AttributesWidget, self).__init__(attributes, parent = None)
            self._refreshMode()
                    
        # ---------------------------------------- #
            
        def _onFieldChanged(self, field_index, val):
            if field_index == TFCnnBenchmarksStep.ATTRIBUTE_ID_MODE:
                self._setMode(val)
            DefaultAttributesWidget._onFieldChanged(self, field_index, val)
        
        # ---------------------------------------- #
        
        def _setMode(self, val):
            if val in TFCnnBenchmarksStep.MODE_NAMES:
                mode = TFCnnBenchmarksStep.MODE_NAMES.index(val)
            else:
                mode = TFCnnBenchmarksStep.MODE_NAMES[0]
                self._setFieldValue(TFCnnBenchmarksStep.ATTRIBUTE_ID_MODE, mode)
                
            is_parameter_server       = (mode == TFCnnBenchmarksStep.MODE_PARAMETER_SERVER)
            is_distributed_all_reduce = (mode == TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE)
            is_horovod                = (mode == TFCnnBenchmarksStep.MODE_HOROVOD)
            is_local                  = (mode == TFCnnBenchmarksStep.MODE_LOCAL)
            
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_ALL_REDUCE_SPECS, is_distributed_all_reduce)
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_CONTROLLER, is_distributed_all_reduce)
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_PS, is_parameter_server)
            self._showField(TFCnnBenchmarksStep.ATTRIBUTE_ID_SERVER_PROTOCOL, not is_local and not is_horovod)
        
        # ---------------------------------------- #
        
        def _refreshMode(self):
            mode = self._getFieldValue(TFCnnBenchmarksStep.ATTRIBUTE_ID_MODE)
            self._setMode(mode)
       
        # ---------------------------------------- #
        
        def load(self, values):
            DefaultAttributesWidget.load(self, values)
            mode = self._getFieldValue(TFCnnBenchmarksStep.ATTRIBUTE_ID_MODE)
            self._setMode(mode)

    # -------------------------------------------------------------------- #
    
    WIDGET_CLASS = AttributesWidget

    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        Step.__init__(self, values)

    # -------------------------------------------------------------------- #
    
    def attributesRepr(self):
        if self.mode == TFCnnBenchmarksStep.MODE_LOCAL:
            return "%s, LOCAL, %u GPU, batch %u" % (self.model,
                                                    self.num_gpus,
                                                    self.batch_size)
        else:
            return "%s, %s, %u GPUs, batch %u" % (self.model,
                                                  self.server_protocol,
                                                  self.num_gpus * len(self.workers),
                                                  self.batch_size) 

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
        self._performance_table.addColumn(FormattedTable.Column("CPU time", 9), "Performance")
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
        for process in self._processes:
            if process.perf is not None:
                # Append to global performance results:
                self._perf.reduce(process.perf)
        
        log("Appending to results file: %s" % self._performance_file.name) 
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
               self._perf.port_rcv_errors.val,
               self._perf.port_rcv_constraint_errors.val]
        self._performance_table.addRow(row)
        self._performance_table.unbind()
        self._performance_file.close()
        
        summary_table = self._performance_table.cut(["Performance", "RX/TX rate (Mbit/sec)", "Network Errors"])
        summary_table.printFormatted(LogWriter(None, LOG_LEVEL_NOTE))

    # -------------------------------------------------------------------- #
    
    def _getOrCreateServer(self, hostname, ip):
        if hostname in self._servers:
            return self._servers[hostname]
        server = ServerInfo(ip, hostname)
        self._servers[hostname] = server
        return server

    # -------------------------------------------------------------------- #
    
    def _initServerMonitors(self, server):
        server.graphs_dir = os.path.join(self._logs_dir, "graphs", toFileName(server.hostname))
        server.remote_graphs_dir = os.path.join(self._work_dir, "graphs")
        if not os.path.exists(server.graphs_dir):
            os.makedirs(server.graphs_dir)
        remote_monitor_title = lambda process: "Monitor [%s]" % process.server
        remote_monitor_bin = "ml_monitor"
        
        monitored_pids = ",".join(["%u" % p.remote_pid for p in server.processes])
        monitored_nics = ",".join(["%s:%u" % (p.rdma_device.name, p.rdma_device.port) for p in server.processes])
        remote_monitor_flags = "--cpu %s 0.010 --gpu 0.020 --net %s 0.010 --net_errors %s 1 -d %s" % (monitored_pids, 
                                                                                                      monitored_nics,
                                                                                                      monitored_nics,
                                                                                                      server.remote_graphs_dir)
        server.monitor_log_path = os.path.join(server.graphs_dir, "monitor.log") 
        server.monitor = RemoteMonitor(server.hostname, remote_monitor_bin, remote_monitor_flags, remote_monitor_title, server.monitor_log_path)
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
        self.runSCP([server_info.remote_graphs_dir], server_info.graphs_dir, src_servers=[server_info.hostname])
        return res
    
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
        log_level = LOG_LEVEL_NOTE if process.is_worker and process.task_id == 0 else LOG_LEVEL_INFO
        process.table.bind(LogWriter(process, log_level))
    
    # -------------------------------------------------------------------- #
    
    def _finishProcessReport(self, process):
        if process.server_info.monitor is not None:
            process.server_info.monitor.fillMeasurement(process.perf.stime)
            process.server_info.monitor.fillMeasurement(process.perf.utime)
            process.server_info.monitor.fillMeasurement(process.perf.rx)
            process.server_info.monitor.fillMeasurement(process.perf.tx)
            process.server_info.monitor.fillMeasurement(process.perf.excessive_buffer_overrun_errors)
            process.server_info.monitor.fillMeasurement(process.perf.port_xmit_discards)
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
    
    def _findRemoteProcessIDs(self, processes):
        remote_process_ids = {}
        def parser(line, find_process):
            debug(line)
            key = find_process.name
            remote_process_ids[key] = int(line.split()[0])
       
        res = True
        num_attempts = 0
        max_num_attempts = 3
        while len(remote_process_ids) < len(processes):
            find_processes = []
            for process in processes:
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
            
        for process in processes:
            if process.name in remote_process_ids:
                process.remote_pid = remote_process_ids[process.name]
            else:
                process.remote_pid = -1
        return res
    
    # -------------------------------------------------------------------- #
    
    def _printProcessSummary(self, processes):
#         table = FormattedTable()
#         table.border_style = UniBorder.BORDER_STYLE_SINGLE
#         table.addColumn(FormattedTable.Column("IP"))
#         table.addColumn(FormattedTable.Column("Job"))
#         table.addColumn(FormattedTable.Column("PID"))
#         table.addColumn(FormattedTable.Column("RPID"))
#         table.addColumn(FormattedTable.Column("Flags"))
#         table.addColumn(FormattedTable.Column("Command"))
        log("")
        log("<table border=1>")
        log("<tr>")
        log("    <th>%s</th>" % "IP")
        log("    <th>%s</th>" % "Job")
        log("    <th>%s</th>" % "PID")
        log("    <th>%s</th>" % "RPID")
        log("    <th>%s</th>" % "Flags")
        log("    <th>%s</th>" % "Command")
        log("</tr>")
        for process in processes:
#             table.addRow([process.server_info.ip, process.name, process.instance.pid, process.remote_pid, process.tf_flags, process.tf_command])
            log("<tr>")
            log("    <td>%s</td>" % process.server_info.ip)
            log("    <td><a href=\"%s\">%s</a></td>" % (process.log_file_path, process.name))
            log("    <td>%s</td>" % process.instance.pid)
            log("    <td>%s</td>" % process.remote_pid)
            log("    <td>%s</td>" % process.tf_flags)
            log("    <td>%s</td>" % process.tf_command)
            log("</tr>")
#         table.printFormatted(LogWriter(None, LOG_LEVEL_NOTE))
        log("</table>")
        log("")
    
    # -------------------------------------------------------------------- #
            
    def _getDevices(self, ips):
        links = {}
        self._devices = {}
        
        def linkNameParser(line, process):
            debug(line, process)
            links[process.server] = line
        
        def deviceNameAndPortParser(line, process):
            debug(line, process)
            parts = line.split()
            res = RemoteDeviceInfo()
            res.name = parts[0]
            res.port = int(parts[2])
            res.is_up = parts[5] == "(Up)"
            self._devices[process.server] = res

        procs = []
        for ip in ips:
            server = TestEnvironment.Get().getServer(ip)
            procs.extend(executeRemoteCommand([server], "ip -o a s | grep %s | cut -d ' ' -f 2 | cut -d'.' -f1" % ip))
        if not waitForProcesses(procs, wait_timeout=5, on_output=linkNameParser):
            for proc in procs:
                if proc.exception is not None:
                    raise proc.exception
            raise Exception("Internal Error")
        
        procs = []
        for ip in ips:
            server = TestEnvironment.Get().getServer(ip)
            link = links.get(server)
            if not link:
                error("IP %s: No device found." % ip)
                continue
            procs.extend(executeRemoteCommand([server], "ibdev2netdev | grep %s" % link))
        
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

    # -------------------------------------------------------------------- #
    
    def _runJob(self, work_dir, ip, job_name, task_id):
        hostname = TestEnvironment.Get().getServer(ip)
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
        if self.mode == TFCnnBenchmarksStep.MODE_HOROVOD:
            if task_id == 0: 
                tf_command += "mpirun -H %s" % ",".join(["%s:%u" % (TestEnvironment.Get().getServer(wip), self.num_gpus) for wip in self.workers])
                tf_command += " -bind-to none -map-by slot"
                tf_command += " -x NCCL_DEBUG=INFO -x LD_LIBRARY_PATH -x PATH"
                tf_command += " -mca pml ob1 -mca btl ^openib -- "
            else:
                return None
  
        # tf_command += " gdb --args"
        tf_command += "python -u %s/tf_cnn_benchmarks.py" % self._work_dir
        if self.mode in [TFCnnBenchmarksStep.MODE_PARAMETER_SERVER,
                         TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE]:
            tf_command += " --job_name=%s" % job_name
            tf_command += " --task_index=%u" % task_id
            tf_command += " --worker_hosts=%s" % self._cluster_workers
        
        if self.mode in [TFCnnBenchmarksStep.MODE_PARAMETER_SERVER]:
            tf_command += " --ps_hosts=%s" % self._cluster_ps
        elif self.mode in [TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE]:
            tf_command += " --variable_update=distributed_all_reduce"
            tf_command += " --all_reduce_spec=%s" % self.all_reduce_spec
        elif self.mode in [TFCnnBenchmarksStep.MODE_HOROVOD]:
            tf_command += " --variable_update=horovod"
        

        if job_name in ["worker", "controller"]:
            tf_command += " --model=%s" % self.model
            tf_command += " --batch_size=%s" % self.batch_size
            if self.data_dir != "":
                tf_command += " --data_dir=%s" % self.data_dir
            if (self.num_gpus > 0) and (self.mode != TFCnnBenchmarksStep.MODE_HOROVOD):
                tf_command += " --num_gpus=%s --local_parameter_device=gpu" % self.num_gpus
            if self.trace_file:
                tf_command += " --trace_file=%s" % os.path.join(self._work_dir, "trace_%s_%u.json" % (job_name, task_id))
        
        if self.mode in [TFCnnBenchmarksStep.MODE_PARAMETER_SERVER,
                         TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE]:
            tf_command += " --server_protocol=%s" % self.server_protocol
        
        if self.forward_only:
            tf_command += " --forward_only"

        if self.model_graph_file and (task_id == 0):
            tf_command += " --graph_file=%s" % os.path.join(self._work_dir, "graph.txt")

        command = tf_flags + " " + tf_command

        title = "[%s] %s - %u" % (ip, job_name, task_id)
        log_file_path = os.path.join(self._logs_dir, "%s_%u.log" % (job_name, task_id))
        factory = BasicProcess.getFactory(title, log_file_path)
        process = executeRemoteCommand([server_info.hostname], command, factory = factory)[0]
        process.name = "%s_%u" % (job_name, task_id)
        process.job_name = job_name 
        process.task_id = task_id
        process.is_worker = job_name == "worker"
        process.rdma_device = device_info
        process.server_info = server_info
        process.tf_flags = tf_flags
        process.tf_command = tf_command
        process.remote_pid = None
        process.perf = None
        self._processes.append(process)
        server_info.processes.append(process)
        return process

    # -------------------------------------------------------------------- #
    
    def _onOut(self, line, process):
        if "Running warm up" in line:
            log(line, process)
            self._initProcessReport(process)
            if not self._startServerMonitors(process.server):
                warning("Warning: Failed to start monitor for server %s.\n" % process.server)
                process.server_info.monitor = None 
                #self.stop()
                #return
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
        
        log("[%s]: Process %s is done." % (process.server_info.ip, process.name))
        res = process.instance.returncode in [0, 143, -15]
        with self._process_done_lock:
            if not res:
                self._stopAllIfNotAlreadyStopping()
            if process.is_worker:
                self._num_finished_workers += 1
                if self._num_finished_workers == len(self.workers):
                    log("All workers are done. Stopping remaining processes.")
                    self._stopAllIfNotAlreadyStopping()
        return res
    
    def _stopAllIfNotAlreadyStopping(self):
        if not self._stopping:
            self._stopping = True
            self._stopAll()
    
    # -------------------------------------------------------------------- #

    def _stopAll(self):
        log("Stopping processes:")
        for process in self._processes:
            if process.remote_pid and process.isAlive():
                log("Stopping [%s] %s: %u" % (process.server, process.name, process.instance.pid))
                os.kill(process.instance.pid, 15)
                self.runInline("kill -15 %u >& /dev/null" % process.remote_pid, servers=[process.server])
        log("Done.")
    
    # -------------------------------------------------------------------- #
    
    def _getIPs(self):
        if self.mode == TFCnnBenchmarksStep.MODE_LOCAL:
            res = [self.workers[0]]
        elif self.mode == TFCnnBenchmarksStep.MODE_PARAMETER_SERVER:
            res = list(set(self.ps + self.workers))
        elif self.mode == TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE:
            res = list(set(self.controller + self.workers))
        else:
            res = list(set(self.workers))
        return sorted(res)
    
    # -------------------------------------------------------------------- #

    def perform(self, index):
        Step.perform(self, index)
        log("<br><img src='%s' width=600 style='border:1px solid black'/><br>" % _res("images/tensorflow.jpg")) #https://www.skylinelabs.in/blog/images/tensorflow.jpg?width=500'/>")
        for attr in self._attributes:
            log(" + %s: %s" % (attr.desc.display_name, str(attr.val)))
        self._perf = TFPerformanceMeasurements()
        self._processes = []
        self._stopping = False
        self._process_done_lock = threading.Lock()
        self._num_finished_workers = 0 
        self._servers = {}
        work_dir_name = "tmp." + next(tempfile._get_candidate_names()) + next(tempfile._get_candidate_names())
        work_dir = os.path.join(tempfile._get_default_tempdir(), work_dir_name)
        script_dir = os.path.dirname(self.script)
        
        user = getuser()
        self._work_dir = work_dir
        ips = self._getIPs()
        servers = TestEnvironment.Get().getServers(ips)
            
        #########################
        # Kill other instances: #
        #########################
        apps_to_kill = ["tf_cnn_benchmarks.py", "ml_monitor"]
        for app in apps_to_kill:
            kill_cmd = "ps -f | grep %s | grep -v grep | grep -v %s | sed -e 's@%s *\\([0-9]\\+\\) .*@\\1@g' | xargs kill -9" % (app, work_dir, user)
            res = self.runInline(kill_cmd, servers, wait_timeout = 5)
            if not res:
                return False
        if self._stop:
            return False
    
        #########
        # Copy: #
        #########
        title("Copying scripts:", style = 3)
        if not self.runSCP([script_dir], work_dir, dst_servers=servers, wait_timeout = 10): # Also create it
            return False
        if self._stop:
            return False
            
        ########
        # Run: #
        ########
        self._openPerformanceFile()
        self._buildCluster()
        if not self._getDevices(ips):
            return False
        
        title("Running:", style = 3)
        processes = []
        if self.mode == TFCnnBenchmarksStep.MODE_PARAMETER_SERVER:
            for i in range(len(self.ps)):
                ip = self.ps[i]
                process = self._runJob(work_dir, ip, "ps", i)
                if process:
                    processes.append(process)
        elif self.mode == TFCnnBenchmarksStep.MODE_DISTRIBUTED_ALL_REDUCE:
            process = self._runJob(work_dir, ip, "controller", 0)
            if process:
                processes.append(process) 
        ################
        # Run workers: #
        ################
        if self.mode == TFCnnBenchmarksStep.MODE_LOCAL:
            process = self._runJob(work_dir, self.workers[0], "worker", 0)
            if process:
                processes.append(process)
        else:
            for i in range(len(self.workers)):
                ip = self.workers[i]
                process = self._runJob(work_dir, ip, "worker", i)
                if process:
                    processes.append(process)
        
        time.sleep(0.2)
        res = self._findRemoteProcessIDs(processes)
        if self._stop:
            return False
        self._printProcessSummary(processes)
        
        if res:
            if self.mode != TFCnnBenchmarksStep.MODE_HOROVOD:
                for server in self._servers.values():
                    if not self._initServerMonitors(server):
                        return False

        title("Waiting for processes to end:", style = 3)
        res = waitForProcesses(processes, 
                               wait_timeout=1800,
                               on_output=self._onOut,
                               on_process_start=self._onJobStart,
                               on_process_done=self._onJobDone)

        for server in self._servers.values():
            res = res and self._stopServerMonitors(server)
        
        if not res or self._stop:
            return False

        self._appendToPerformanceFile()
        
        ############
        # Cleanup: #
        ############
        title("Cleaning:", style = 3)
        self.runSCP(["%s/graph.txt" % self._work_dir, "%s/*.json" % self._work_dir], self._logs_dir, src_servers=servers, wait_timeout=10)
        return True

    # -------------------------------------------------------------------- #
    
    def stop(self):
        Step.stop(self)
        self._stopAllIfNotAlreadyStopping()
