#!/usr/bin/python
# -*- coding: utf-8 -*-

import threading
import os
import time
from Actions.Util import executeCommand, waitForProcesses, executeRemoteCommand
import sys
import re
from Actions.FormattedTable import FormattedTable
from Actions.Log import log

###############################################################################

class StatsValue(object):
    def __init__(self):
        self.val = 0.0
        self.total = 0.0
        self.count = 0
        self.min = float("inf")
        self.max = float("-inf")
        self.avg = 0.0
        self.time = 0
        self.samples = []
    
    # -------------------------------------------------------------------- #
    
    def update(self, val):
        self.val = val
        self.total += val
        self.count += 1
        self.min = min(val, self.min)
        self.max = max(val, self.max)
        self.avg = self.total / self.count
        self.time = time.time()
        
    # -------------------------------------------------------------------- #
    
    def reduce(self, other):
        self.total += other.total
        self.count += other.count
        self.avg = self.total / self.count
        self.min = min(self.min, other.min)
        self.max = max(self.max, other.max)
        if self.time < other.time:
            self.time = other.time
            self.val = other.val    
        
###############################################################################

class Measurement(StatsValue):
    
    def __init__(self, name, measure_rate = False):
        super(Measurement, self).__init__()
        self.name = name
        if measure_rate:
            self.rate = StatsValue()
        else:
            self.rate = None
    
    # -------------------------------------------------------------------- #
    
    def update(self, val):
        if (self.rate is not None) and (self.count > 0):
            dx = val - self.val
            dy = time.time() - self.time # time in seconds
            rate = dx / dy
            self.rate.update(rate)
        StatsValue.update(self, val)
        
    # -------------------------------------------------------------------- #
    
    def reduce(self, other):
        if (self.rate is not None) and (other.rate is not None):
            self.rate.reduce(other.rate)
        StatsValue.reduce(self, other)
        
###############################################################################
        
class CommonPerformanceMeasurements(object):
    def __init__(self):
        self.gpu = Measurement("GPU")
        self.cpu = Measurement("CPU")
        self.mem = Measurement("MEM")
        self.rx = Measurement("RDTA", True)
        self.tx = Measurement("TDTA", True)
    
    # -------------------------------------------------------------------- #
    
    def reduce(self, other):
        self.gpu.reduce(other.gpu)
        self.cpu.reduce(other.cpu)
        self.mem.reduce(other.mem)
        self.rx.reduce(other.rx)
        self.tx.reduce(other.tx)

###############################################################################

class Monitor(object):
    
    def __init__(self, server = None, out = None, time_interval = 0.1, log_ratio = 30):
        self._server = server
        self._out = out
        self._time_interval = time_interval
        self._log_ratio = log_ratio
        self._samplers = []
        self._measurements = []
        self._measurements_by_name = {}

    # -------------------------------------------------------------------- #

    def addSampler(self, sampler):
        sampler._server = self._server
        self._samplers.append(sampler)
        for measurement in sampler.getMeasurements():
            self._measurements.append(measurement)
            self._measurements_by_name[measurement.name] = measurement
        
    # -------------------------------------------------------------------- #
    
    def start(self):
        if self._out is not None:
            self._table = FormattedTable()
            for measurement in self._measurements:            
                group_name = measurement.name
                self._table.add_column(FormattedTable.Column("val", min_width=6), group_name)
                self._table.add_column(FormattedTable.Column("avg", min_width=6), group_name)
                self._table.add_column(FormattedTable.Column("min", min_width=6), group_name)
                self._table.add_column(FormattedTable.Column("max", min_width=6), group_name)
                if measurement.rate is not None:
                    group_name = measurement.name + "-Rate"
                    self._table.add_column(FormattedTable.Column("val", min_width=6), group_name)
                    self._table.add_column(FormattedTable.Column("avg", min_width=6), group_name)
                    self._table.add_column(FormattedTable.Column("min", min_width=6), group_name)
                    self._table.add_column(FormattedTable.Column("max", min_width=6), group_name)
            self._table.bind(self._out)

        self._stop = False
        self._thread = threading.Thread(target=self.doMonitor)
        self._thread.start()
        
    # -------------------------------------------------------------------- #

    def stop(self):
        if not self.isRunning():
            return

        self._stop = True
        self._thread = None
        if self._out is not None:
            self._table.unbind()
        
    # -------------------------------------------------------------------- #
    
    def isRunning(self):
        return self._thread is not None
        
    # -------------------------------------------------------------------- #
    
    def log(self, count):
        if self._out is None:
            return
        
        row = []
        for measurement in self._measurements:
            row.append("%.2lf" % measurement.val)
            row.append("%.2lf" % measurement.avg)
            row.append("%.2lf" % measurement.min)
            row.append("%.2lf" % measurement.max)
            if measurement.rate is not None:
                row.append("%.2lf" % measurement.rate.val)
                row.append("%.2lf" % measurement.rate.avg)
                row.append("%.2lf" % measurement.rate.min)
                row.append("%.2lf" % measurement.rate.max)
        self._table.add_row(row)
    
    # -------------------------------------------------------------------- #
    
    def doMonitor(self):
        count = 0
        while not self._stop:
            for sampler in self._samplers:
                if not sampler.update():
                    self.stop()
                    return
            if count % self._log_ratio == 0:
                self.log(count)
            time.sleep(self._time_interval)
            count += 1

    # -------------------------------------------------------------------- #

    def measurements(self):
        return self._measurements
    
    # -------------------------------------------------------------------- #
    
    def __getitem__(self, measurement_name):
        return self._measurements_by_name[measurement_name]
 

###############################################################################

class Sampler(object):
    ''' A sampler creates and manages 1 or more measurements. '''
    def __init__(self):
        self._server = None
        self._measurements = []
    
    # -------------------------------------------------------------------- #
    
    def getMeasurements(self):
        ''' Return a list of performance measurements. '''
        return self._measurements
    
    # -------------------------------------------------------------------- #
    
    def update(self):
        ''' Update performance measurements. '''
        raise Exception("Unimplemented monitorAction")
    
    # -------------------------------------------------------------------- #
    
    def _runCommand(self, cmd, parser):
        if self._server is None:
            processes = [executeCommand(cmd, verbose=False)]
        else:
            processes = executeRemoteCommand([self._server], cmd, verbose=False)
        self._parser_error = False
        return waitForProcesses(processes, on_output=parser, verbose=False) and not self._parser_error
    

###############################################################################

class GPUSampler(Sampler):

    def __init__(self):
        super(GPUSampler, self).__init__()
    
    # -------------------------------------------------------------------- #
    
    def getMeasurements(self):
        if len(self._measurements) == 0:
            self.update()
        return self._measurements
        
    # -------------------------------------------------------------------- #
            
    def update(self):
        results = []
        def parser(line, process):
            m = re.search(" [0-9]+% ", line)
            if m is not None:
                results.append(float(m.group(0)[1:-2]))
        
        if not self._runCommand("nvidia-smi", parser):
            return False
        
        if len(self._measurements) == 0:
            for i in range(len(results)):
                self._measurements.append(Measurement("GPU-%u" % i))
        else:
            for i in range(len(results)):
                val = results[i]
                self._measurements[i].update(val)            
        return True
    
###############################################################################

class CPUAndMemSampler(Sampler):

    def __init__(self, pid):
        super(CPUAndMemSampler, self).__init__()
        self._pid = pid
        self._cpu = Measurement("CPU")
        self._mem = Measurement("MEM")
        self._measurements = [self._cpu, self._mem]
    
    # -------------------------------------------------------------------- #
            
    def update(self):
        def parser(line, process):
            split = line.split()
            try:
                self._cpu.update(float(split[8]))
                self._mem.update(float(split[9]))
            except:
                self._parser_error = True
            
        cmd = "top -b -p %u -n 1 | tail -1" % self._pid
        return self._runCommand(cmd, parser)
    
###############################################################################
 
class RXTXSampler(Sampler):
 
    def __init__(self, device, port):
        super(RXTXSampler, self).__init__()
        self._device = device
        self._port = port
        self._rpkt = Measurement("RPKT", True)
        self._rdta = Measurement("RDTA", True)
        self._tpkt = Measurement("TPKT", True)
        self._tdta = Measurement("TDTA", True)
        self._measurements = [self._rpkt, self._rdta, self._tpkt, self._tdta]
     
    # -------------------------------------------------------------------- #
             
    def update(self):
        counters_dir = os.path.join("/sys", "class", "infiniband", self._device, "ports", str(self._port), "counters")
        rpkt_path = os.path.join(counters_dir, "port_rcv_packets")
        rdta_path = os.path.join(counters_dir, "port_rcv_data")
        tpkt_path = os.path.join(counters_dir, "port_xmit_packets")
        tdta_path = os.path.join(counters_dir, "port_xmit_data")
        rpkt = int(open(rpkt_path, "r").read())
        rdta = int(open(rdta_path, "r").read()) * 4 * 8 / 1000000.0
        tpkt = int(open(tpkt_path, "r").read())
        tdta = int(open(tdta_path, "r").read()) * 4 * 8 / 1000000.0
        self._rpkt.update(rpkt)
        self._rdta.update(rdta)
        self._tpkt.update(tpkt)
        self._tdta.update(tdta)
#         print "RPKT: %u. RDTA: %u. TPKT: %u. TDTA: %u" % (rpkt, rdta, tpkt, tdta)
        
#         rpkt=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_rcv_packets`
#         rdta=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_rcv_data`
#         rpktd=$((rpkt - rpktold))
#         rdtad=$((rdta - rdtaold))
#         rmbps=$((rdtad * 4 * 8 / 1000 / 1000))
#         total_rmbps=`python -c "print $total_rmbps + $rmbps"`
#     
#         tpkt=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_xmit_packets`
#         tdta=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_xmit_data`
#         tpktd=$((tpkt - tpktold))
#         tdtad=$((tdta - tdtaold))
#         tmbps=$((tdtad * 4 * 8 / 1000 / 1000))
#         total_tmbps=`python -c "print $total_tmbps + $tmbps"`
#     
#         rpktold=$rpkt; rdtaold=$rdta;
#         tpktold=$tpkt; tdtaold=$tdta;
                     
        return True
       
###############################################################################################################################################################
#
#                                                                         APP
#
###############################################################################################################################################################

       
if __name__ == '__main__':
    #prompt.setData([[7,0,1,2],[8,3,4,5]], ["R","F","G","H"], ["S","T"])
#    file_path = "/tmp/test.csv"
    #monitor = CPUMontior("12.12.12.25", 1, sys.stdout, sample_ratio=30)
    cmd = "bash -c 'for i in {1..1000000}; do echo $i >& /dev/null; done'"
    process = executeCommand(cmd)
    
    monitor = Monitor(server = None, out = sys.stdout, log_ratio=1)
    monitor.addSampler(GPUSampler())
    monitor.addSampler(CPUAndMemSampler(process.instance.pid))
    monitor.addSampler(RXTXSampler("mlx5_0", 1))
    print "Monitor starting..."
    monitor.start()
    waitForProcesses([process], wait_timeout = 10, verbose=False)
    monitor.stop()
    print "Monitor stopped."
#    print "See: %s" % file_path
