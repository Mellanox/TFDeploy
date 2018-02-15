#!/usr/bin/python
# -*- coding: utf-8 -*-

import threading
import os
import time
import sys
import re
import argparse
import cmd

from Common.Util import executeCommand, waitForProcesses
from Common.FormattedTable import FormattedTable

###############################################################################

def _printVal(val):
    if isinstance(val, float):
        return "%.2lf" % val
    else:
        return "%u" % val

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
        self.avg = 0 if self.count is 0 else self.total / self.count
        self.time = time.time()
        
    # -------------------------------------------------------------------- #
    
    def reduce(self, other):
        self.total += other.total
        self.count += other.count
        self.avg = 0 if self.count is 0 else self.total / self.count
        self.min = min(self.min, other.min)
        self.max = max(self.max, other.max)
        if self.time < other.time:
            self.time = other.time
            self.val = other.val    
        
###############################################################################

class Measurement(StatsValue):
    
    FLOAT_PRINTER = lambda x: "%.2lf" % x
    INT_PRINTER = lambda x: "%u" % x
    
    def __init__(self, 
                 name,
                 units = "", 
                 measure_rate = False, 
                 width = 6,
                 rate_width = 6):
                 
        super(Measurement, self).__init__()
        self.name = name
        self.units = units
        self.width = width
        self.rate_width = rate_width
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
    
    # -------------------------------------------------------------------- #
    
    def appendToTableHeaders(self, table):
        group_name = self.name
        if self.units != "":
            group_name += " (" + self.units + ")"
        table.addColumn(FormattedTable.Column("#", min_width=7), group_name)
        table.addColumn(FormattedTable.Column("val", min_width=self.width), group_name)
        table.addColumn(FormattedTable.Column("avg", min_width=self.width), group_name)
        table.addColumn(FormattedTable.Column("min", min_width=self.width), group_name)
        table.addColumn(FormattedTable.Column("max", min_width=self.width), group_name)
        if self.rate is not None:
            group_name = self.name + "-Rate"
            if self.units != "":
                group_name += " (" + self.units + "/sec)"
            table.addColumn(FormattedTable.Column("val", min_width=self.rate_width), group_name)
            table.addColumn(FormattedTable.Column("avg", min_width=self.rate_width), group_name)
            table.addColumn(FormattedTable.Column("min", min_width=self.rate_width), group_name)
            table.addColumn(FormattedTable.Column("max", min_width=self.rate_width), group_name)
    
    # -------------------------------------------------------------------- #
    
    def appendToTableRow(self, row):
        row.append(_printVal(self.count))
        row.append(_printVal(self.val))
        row.append(_printVal(self.avg))
        row.append(_printVal(self.min))
        row.append(_printVal(self.max))
        if self.rate is not None:
            row.append(_printVal(self.rate.val))
            row.append(_printVal(self.rate.avg))
            row.append(_printVal(self.rate.min))
            row.append(_printVal(self.rate.max))
                    
###############################################################################

class NetErrorMeasurments(object):
    def __init__(self):
        self.excessive_buffer_overrun_errors   = Measurement("XBUF_OVERRUN_ERRORS")
        self.port_xmit_discards                = Measurement("PORT_XMIT_DISCARDS")
        self.port_rcv_errors                   = Measurement("PORT_RCV_ERRORS")
        self.port_rcv_constraint_errors        = Measurement("PORT_RCV_CONSTRAINT_ERRORS")

    # -------------------------------------------------------------------- #
    
    def reduce(self, other):
        self.excessive_buffer_overrun_errors.reduce(other.excessive_buffer_overrun_errors)
        self.port_xmit_discards.reduce(other.port_xmit_discards)
        self.port_rcv_errors.reduce(other.port_rcv_errors)
        self.port_rcv_constraint_errors.reduce(other.port_rcv_constraint_errors)
        
###############################################################################
        
class CommonPerformanceMeasurements(object):
    def __init__(self):
        self.gpu = Measurement("GPU", "%")
        self.cpu = Measurement("CPU", "%")
        self.mem = Measurement("MEM", "%")
        self.rx = Measurement("RDTA", "Mbit", True)
        self.tx = Measurement("TDTA", "Mbit", True)
        self.net_erros = NetErrorMeasurments()
    
    # -------------------------------------------------------------------- #
    
    def reduce(self, other):
        self.gpu.reduce(other.gpu)
        self.cpu.reduce(other.cpu)
        self.mem.reduce(other.mem)
        self.rx.reduce(other.rx)
        self.tx.reduce(other.tx)
        self.net_erros.reduce(other.net_erros)

###############################################################################

class StickyCounter(object):
    
    def __init__(self, sampler, measurement, file_path, parser=int):
        self.sampler = sampler
        self.measurement = measurement
        self.file_path = file_path
        self.parser = parser
    
    # -------------------------------------------------------------------- #
    
    def _readVal(self):
        with open(self.file_path, "r") as f:
            return self.parser(f.read())
        
    # -------------------------------------------------------------------- #
    
    def resetBase(self):
        #with open(self.file_path, "r") as f:
        self._base_value = self._readVal()
        
    # -------------------------------------------------------------------- #
    
    def update(self):
        value = self._readVal()
        self.measurement.update(value - self._base_value)

###############################################################################

class Sampler(object):
    ''' A sampler creates and manages 1 or more measurements. '''
    def __init__(self, delay = 0, graph_dir = None):
        self._measurements = []
        self._delay = delay
        self._graph_dir = graph_dir
        self._graphs = []
        self._thread = None
        if (graph_dir is not None) and (not os.path.isdir(graph_dir)):
            os.makedirs(graph_dir)
        
    # -------------------------------------------------------------------- #
    
    def getMeasurements(self):
        ''' Return a list of performance measurements. '''
        return self._measurements
    
    # -------------------------------------------------------------------- #
    
    def _openGraphs(self):
        self._graphs = []
        if self._graph_dir is None:
            return
        for measurement in self._measurements:
            graph_file_path = os.path.join(self._graph_dir, measurement.name + ".csv")
            graph_file = open(graph_file_path, "w")
            #table = FormattedTable()
            #measurement.appendToTableHeaders(table)
            #table.bind(graph_file, type = FormattedTable.TYPE_CSV)
            #self._graphs.append(table)
            self._graphs.append(graph_file)
            
    # -------------------------------------------------------------------- #
    
    def _appendToGraphs(self):
        for i in range(len(self._graphs)):
            measurement = self._measurements[i]
            #table = self._graphs[i]
            #row = [measurement.time, measurement.val]
            #table.addRow(row)
            self._graphs[i].write("%.3lf, %u\n" % (measurement.time, measurement.val))

    # -------------------------------------------------------------------- #
    
    def _closeGraphs(self):
#         for table in self._graphs:
#             table.unbind()
#             table.output.close()
        for graph in self._graphs:
            graph.close()

    # -------------------------------------------------------------------- #
    
    def start(self):
        if self._thread is not None:
            return
        
        self._openGraphs()        
        self._stop = False
        self._thread = threading.Thread(target=self._sampleInLoop)
        self._thread.start()        
        
    # -------------------------------------------------------------------- #
    
    def _sampleInLoop(self):
        while not self._stop:
            self._sample()
            self._appendToGraphs()
            time.sleep(self._delay)

    # -------------------------------------------------------------------- #
    
    def _sample(self):
        ''' Update performance measurements. '''
        raise Exception("Unimplemented monitorAction")

    # -------------------------------------------------------------------- #
    
    def _runCommand(self, cmd, parser):
        processes = [executeCommand(cmd, verbose=False)]
        self._parser_error = False
        return waitForProcesses(processes, on_output=parser, verbose=False) and not self._parser_error
    
    # -------------------------------------------------------------------- #
    
    def stop(self):
        self._stop = True
        
    # -------------------------------------------------------------------- #
    
    def waitForStop(self, timeout):
        if self._thread is None:
            return
        
        self._thread.join(timeout)
        self._thread = None
        self._closeGraphs()

###############################################################################

class GPUSampler(Sampler):

    def __init__(self, delay = 0, graph_dir = None):
        super(GPUSampler, self).__init__(delay, graph_dir)
    
    # -------------------------------------------------------------------- #
    
    def getMeasurements(self):
        if len(self._measurements) == 0:
            self._sample()
        return self._measurements
        
    # -------------------------------------------------------------------- #
            
    def _sample(self):
        results = []
        def parser(line, process):
            m = re.search(" [0-9]+% ", line)
            if m is not None:
                results.append(float(m.group(0)[1:-2]))
        
        if not self._runCommand("nvidia-smi", parser):
            return False
        
        if len(self._measurements) == 0:
            for i in range(len(results)):
                self._measurements.append(Measurement("GPU-%u" % i, "%"))
        else:
            for i in range(len(results)):
                val = results[i]
                self._measurements[i].update(val)            
        return True
    
###############################################################################

class CPUAndMemSampler(Sampler):

    def __init__(self, pid, delay = 0, graph_dir = None):
        super(CPUAndMemSampler, self).__init__(delay, graph_dir)
        self._pid = pid
        self._cpu = Measurement("CPU", "%", width=7)
        self._mem = Measurement("MEM", "%")
        self._measurements = [self._cpu, self._mem]
    
    # -------------------------------------------------------------------- #
            
    def _sample(self):
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

def ToMbitParser(val):
    return int(val) * 4 * 8 / 1000000.0

def ToMegaParser(val):
    return int(val) / 1000000.0

###############################################################################

class StickyCounterSampler(Sampler):
  
    def __init__(self, delay, graph_dir = None):
        super(StickyCounterSampler, self).__init__(delay, graph_dir)
        self._counters = []
    
    # -------------------------------------------------------------------- #
    
    def start(self):
        for counter in self._counters:
            counter.resetBase()
        Sampler.start(self)
        
    # -------------------------------------------------------------------- #
             
    def _sample(self):
        for counter in self._counters:
            counter.update()
        return True


###############################################################################

class RXTXSampler(StickyCounterSampler):
  
    def __init__(self, device, port, delay = 0, graph_dir = None):
        super(RXTXSampler, self).__init__(delay, graph_dir)
        self._device = device
        self._port = port
        
        self._rpkt = Measurement("RPKT", "Mpkts", True)
        self._rdta = Measurement("RDTA", "Mbit",  True, width=10, rate_width=8)
        self._tpkt = Measurement("TPKT", "Mpkts", True)
        self._tdta = Measurement("TDTA", "Mbit",  True, width=10, rate_width=8)

        counters_dir = os.path.join("/sys", "class", "infiniband", self._device, "ports", str(self._port), "counters")
        rpkt_path = os.path.join(counters_dir, "port_rcv_packets")
        rdta_path = os.path.join(counters_dir, "port_rcv_data")
        tpkt_path = os.path.join(counters_dir, "port_xmit_packets")
        tdta_path = os.path.join(counters_dir, "port_xmit_data")

        self._counters = []
        self._counters.append(StickyCounter(self, self._rpkt, rpkt_path, ToMegaParser))                           
        self._counters.append(StickyCounter(self, self._rdta, rdta_path, ToMbitParser))
        self._counters.append(StickyCounter(self, self._tpkt, tpkt_path, ToMegaParser))
        self._counters.append(StickyCounter(self, self._tdta, tdta_path, ToMbitParser))
        
        self._measurements = [self._rpkt, self._rdta, self._tpkt, self._tdta]
    
###############################################################################

class NetErrorsSampler(StickyCounterSampler):
  
    def __init__(self, device, port, delay = 0, graph_dir = None):
        super(NetErrorsSampler, self).__init__(delay, graph_dir)
        self._device = device
        self._port = port
        
        self._excessive_buffer_overrun_errors   = Measurement("XBUF_OVERRUN_ERRORS"       , width=8)
        self._port_xmit_discards                = Measurement("PORT_XMIT_DISCARDS"        , width=8)
        self._port_rcv_errors                   = Measurement("PORT_RCV_ERRORS"           , width=8) 
        self._port_rcv_constraint_errors        = Measurement("PORT_RCV_CONSTRAINT_ERRORS", width=8)

        counters_dir = os.path.join("/sys", "class", "infiniband", self._device, "ports", str(self._port), "counters")
        excessive_buffer_overrun_errors_path    = os.path.join(counters_dir, "excessive_buffer_overrun_errors")
        port_xmit_discards_path                 = os.path.join(counters_dir, "port_xmit_discards")
        port_rcv_errors_path                    = os.path.join(counters_dir, "port_rcv_errors")
        port_rcv_constraint_errors_path         = os.path.join(counters_dir, "port_rcv_constraint_errors")

        self._counters = []
        self._counters.append(StickyCounter(self, self._excessive_buffer_overrun_errors, excessive_buffer_overrun_errors_path))
        self._counters.append(StickyCounter(self, self._port_xmit_discards, port_xmit_discards_path ))
        self._counters.append(StickyCounter(self, self._port_rcv_errors, port_rcv_errors_path))
        self._counters.append(StickyCounter(self, self._port_rcv_constraint_errors, port_rcv_constraint_errors_path))
        
        self._measurements = [self._excessive_buffer_overrun_errors,
                              self._port_xmit_discards,
                              self._port_rcv_errors,
                              self._port_rcv_constraint_errors]
    

###############################################################################


###############################################################################

class MonitorShell(cmd.Cmd):
    """Query monitor"""
    
    def __init__(self, monitor):
        cmd.Cmd.__init__(self)
        self.monitor = monitor
        self.prompt = ">>> "

    # -------------------------------------------------------------------- #

    def _start(self):
        self.monitor.start()
    
    # -------------------------------------------------------------------- #
    
    def _stop(self):
        self.monitor.stop()
                
    # -------------------------------------------------------------------- #
        
    def _quit(self):
        self._stop()
        return True

    # -------------------------------------------------------------------- #
    
    def _getStatsAttributes(self, name, stats, args):
        result = []
        if len(args) == 0:
            result.append(name)
            result.append(stats.count)
            result.append(stats.val)
            result.append(stats.total)
            result.append(stats.avg)
            result.append(stats.min)
            result.append(stats.max)
            return result
        
        prop = args[0]
        if prop == "val":
            result.append(stats.val)
        elif prop == "total":
            result.append(stats.total)
        elif prop == "count":
            result.append(stats.count)
        elif prop == "avg":
            result.append(stats.avg)
        elif prop == "min":
            result.append(stats.min)
        elif prop == "max":
            result.append(stats.max)
        return result
    
    # -------------------------------------------------------------------- #
    
    def _getMeasurementAttributes(self, measurement, args):
        result = []
        if len(args) == 0:
            result.extend(self._getStatsAttributes(measurement.name, measurement, args))
            if measurement.rate is not None:
                result.extend(self._getStatsAttributes(measurement.name + "-Rate", measurement.rate, args))
        elif args[0] == "rate":
            if measurement.rate is None:
                print "Error: %s is not defined to measure rate." % measurement.name
                return None
            result.extend(self._getStatsAttributes(measurement.name + "-Rate", measurement.rate, args[1:]))
        else:
            result.extend(self._getStatsAttributes(measurement.name, measurement, args))
        return result
        
    # -------------------------------------------------------------------- #
    
    def _getAttributes(self, line):
        result = []
        if line == "":
            for measurement in self.monitor.measurements():
                res = self._getMeasurementAttributes(measurement, [])
                if res is None:
                    return
                result.extend(res)
            return result   

        phrases = line.split()
        for phrase in phrases:
            args = phrase.split(".")
            measurement_name = args[0]
            if not measurement_name in self.monitor:
                print "Error: No such measurement: '%s'" % measurement_name
                return None
             
            measurement = self.monitor[measurement_name]
            res = self._getMeasurementAttributes(measurement, args[1:])
            if res is None:
                return None
            result.extend(res)
        return result

    # -------------------------------------------------------------------- #
    
    def emptyline(self):
        pass
    
    # -------------------------------------------------------------------- #

    def do_start(self, line):
        self._start()
    
    # -------------------------------------------------------------------- #
    
    def do_stop(self, line):
        self._stop()
            
    # -------------------------------------------------------------------- #
    
    def do_quit(self, line):
        return self._quit()
    
    # -------------------------------------------------------------------- #    
    
    def do_EOF(self, line):
        return self._quit()
    
    # -------------------------------------------------------------------- #
    
    def do_search(self, pattern):
        res = []
        for measurement in self.monitor.measurements():
            if re.search(pattern, measurement.name):
                res.append(measurement.name)
        print " ".join(res)
    
    # -------------------------------------------------------------------- #
    
    def do_print(self, line):
        result = self._getAttributes(line)
        if result is None:
            return
        print " ".join(str(x) for x in result)    
    
###############################################################################
    
class Monitor(object):
    
    def __init__(self):
        self._samplers = []
        self._measurements = []
        self._measurements_by_name = {}
        self._shell = MonitorShell(self)

    # -------------------------------------------------------------------- #

    def addSampler(self, sampler):
        self._samplers.append(sampler)
        for measurement in sampler.getMeasurements():
            self._measurements.append(measurement)
            self._measurements_by_name[measurement.name] = measurement

    # -------------------------------------------------------------------- #
    
    def start(self):
        for sampler in self._samplers:
            sampler.start()

    # -------------------------------------------------------------------- #
    
    def stop(self):
        for sampler in self._samplers:
            sampler.stop()
        for sampler in self._samplers:
            sampler.waitForStop(30)
        
    # -------------------------------------------------------------------- #
    
    def run(self):
#         try:
        self._shell.cmdloop("Monitor terminal... quit or Ctrl+D to stop.")
#         except KeyboardInterrupt:
#             print "\nGot interrupt. stopping..."
        print "Goodbye."

    # -------------------------------------------------------------------- #

    def measurements(self):
        return self._measurements
    
    # -------------------------------------------------------------------- #
    
    def __getitem__(self, measurement_name):
        return self._measurements_by_name[measurement_name]
    
    # -------------------------------------------------------------------- #
    
    def __contains__(self, measurement_name):
        return measurement_name in self._measurements_by_name    
        
###############################################################################################################################################################
#
#                                                                         APP
#
###############################################################################################################################################################
       
if __name__ == '__main__':

    arg_parser = argparse.ArgumentParser(description = "Simple system monitor with few samplers (CPU, GPU, etc...)")
    arg_parser.add_argument("-c", "--cpu", action="append", nargs=2, metavar=("pid", "delay"), help="Enable CPU sampler for process-id")
    arg_parser.add_argument("-g", "--gpu", action="append", nargs=1, metavar=("delay"), help="Enable GPU sampler")
    arg_parser.add_argument("-n", "--net", action="append", nargs=3, metavar=("device", "port", "delay"), help="Enable NET sampler for device and port")
    arg_parser.add_argument("-x", "--net_errors", action="append", nargs=3, metavar=("device", "port", "delay"), help="Enable NET errors sampler for device and port")
#     arg_parser.add_argument("-C", "--print_count", action="store_true", default=False, help="Output sample count.")
#     arg_parser.add_argument("-A", "--print_count", action="store_true", default=True, help="Output sample average.")
#     arg_parser.add_argument("-M", "--print_count", action="store_true", default=True, help="Output sample max.")
#     arg_parser.add_argument("-m", "--print_count", action="store_true", default=True, help="Output sample min.")
    
    arg_parser.add_argument("-d", "--graph_dir", default=None, help="Directory where to put the sample graphs. If empty, no sample graphs will be generated.")
     
    args = arg_parser.parse_args()
    
    graph_dir = args.graph_dir
    monitor = Monitor()
    
    if args.cpu is not None:
        pid = int(args.cpu[0][0])
        delay = float(args.cpu[0][1])
        monitor.addSampler(CPUAndMemSampler(pid, delay, graph_dir))
    if args.gpu is not None:
        delay = float(args.gpu[0][0])
        monitor.addSampler(GPUSampler(delay, graph_dir))
    if args.net is not None:
        device = args.net[0][0]
        port = int(args.net[0][1])
        delay = float(args.net[0][2])
        monitor.addSampler(RXTXSampler(device, port, delay, graph_dir))
    if args.net_errors is not None:
        device = args.net_errors[0][0]
        port = int(args.net_errors[0][1])
        delay = float(args.net_errors[0][2])
        monitor.addSampler(NetErrorsSampler(device, port, delay, graph_dir))

    if len(monitor.measurements()) == 0:
        print "No samplers selected. %s --help for help." % os.path.basename(sys.argv[0])
        sys.exit(1)

    monitor.run()                
