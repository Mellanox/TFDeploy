#!/usr/bin/python
# -*- coding: utf-8 -*-

import threading
import os
import time
from Actions.Util import executeCommand, waitForProcesses, executeRemoteCommand
import sys
import re
from Actions.FormattedTable import FormattedTable

###############################################################################

class PerformanceValue(object):
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
        
###############################################################################

class PerformanceMeasurement(object):
    
    def __init__(self, name, measure_rate = False):
        self.name = name
        self.current = PerformanceValue()
        if measure_rate:
            self.rate = PerformanceValue()
        else:
            self.rate = None
    
    # -------------------------------------------------------------------- #
    
    def update(self, val):
        if (self.rate is not None) and (self.current.count > 0):
            dx = self.current.val - val
            dy = (self.current.time - time.time()) * 1000000.0 # time in seconds
            rate = dx / dy
            self.rate.update(rate)
        self.current.update(val)

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
                if measurement.rate:
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
            row.append("%.2lf" % measurement.current.val)
            row.append("%.2lf" % measurement.current.avg)
            row.append("%.2lf" % measurement.current.min)
            row.append("%.2lf" % measurement.current.max)
            if measurement.rate:
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
                self._measurements.append(PerformanceMeasurement("GPU-%u" % i))
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
        self._cpu = PerformanceMeasurement("CPU")
        self._mem = PerformanceMeasurement("MEM")
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
# 
# class TXRXMontior(Monitor):
# 
#     def __init__(self, server, device, port, out, time_interval = 0.1, sample_ratio = 30):
#         super(CPUMontior, self).__init__(server, out, time_interval, sample_ratio)
#         self._pid = pid
#     
#     # -------------------------------------------------------------------- #
#             
#     def monitorAction(self):
#         results = []
#         def _onOut(line, process):
#             results.append(float(line.split()[8]))
# 
# #         rpkt=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_rcv_packets`
# #         rdta=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_rcv_data`
# #         rpktd=$((rpkt - rpktold))
# #         rdtad=$((rdta - rdtaold))
# #         rmbps=$((rdtad * 4 * 8 / 1000 / 1000))
# #         total_rmbps=`python -c "print $total_rmbps + $rmbps"`
# #     
# #         tpkt=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_xmit_packets`
# #         tdta=`cat /sys/class/infiniband/$RDMA_DEVICE/ports/$RDMA_DEVICE_PORT/counters/port_xmit_data`
# #         tpktd=$((tpkt - tpktold))
# #         tdtad=$((tdta - tdtaold))
# #         tmbps=$((tdtad * 4 * 8 / 1000 / 1000))
# #         total_tmbps=`python -c "print $total_tmbps + $tmbps"`
# #     
# #         rpktold=$rpkt; rdtaold=$rdta;
# #         tpktold=$tpkt; tdtaold=$tdta;
#                     
#         cmd = "top -b -p %u -n 1 | tail -1" % self._pid
#         processes = executeRemoteCommand([self._server], cmd, verbose=False)
#         res = waitForProcesses(processes, on_output=_onOut, verbose=False)
#         if not res:
#             self.stop()
#             return None
#         return results[0]
       
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
    print "Monitor starting..."
    monitor.start()
    waitForProcesses([process], wait_timeout = 10, verbose=False)
    monitor.stop()
    print "Monitor stopped."
#    print "See: %s" % file_path
