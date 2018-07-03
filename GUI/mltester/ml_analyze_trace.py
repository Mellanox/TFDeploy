#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import os
import sys
from commonpylib.util import toFileName

#--------------------------------------------------------------------#

class ProcessInfo(object):
    def __init__(self, pname, output_dir_name):
        self.pname = pname
        self._output_dir_name = output_dir_name 
        self._files = {}
    
    def _getOrCreateLog(self, tid):
        f = self._files.get(tid)
        if not f:
            file_name = "TL-" + toFileName(self.pname) + ("_%u.csv" % tid)
            file_path = os.path.join(self._output_dir_name, file_name)
            print file_path
            f = open(file_path, "w")
            self._files[tid] = f
        return f
    
    def log(self, tid, ts, dur, label):
        f = self._getOrCreateLog(tid)
        f.write("%lf, 0, %s\n" % (ts / 1000000.0, label))
        f.write("%lf, 1\n" % (ts / 1000000.0))
        f.write("%lf, 1\n" % ((ts + dur) / 1000000.0))
        f.write("%lf, 0\n" % ((ts + dur) / 1000000.0))

#--------------------------------------------------------------------#

def analyzeTrace(input_file_path, output_dir):
    processes = {}
    
    
    with open(input_file_path) as f:
        data = json.load(f)
    
    min_ts = sys.maxint
    max_ts = 0
    events = data["traceEvents"]
    for event in events:
        ts = event.get("ts")
        if ts:
            min_ts = min(min_ts, ts)
            max_ts = max(max_ts, ts)
    
    for event in events:
        if event["name"] != "process_name":
            break
        pinfo = ProcessInfo(event["args"]["name"], output_dir)
        pid = int(event["pid"])
        processes[pid] = pinfo
    
    for event in events:
        name = event["name"]
        if name == "process_name":
            continue
        if event["tid"] != 0: # For now only thread 0 is traced
            continue
        if event["cat"] != "Op":
            continue
        
        pid = int(event["pid"])
        tid = int(event["tid"])
        ts = int(event["ts"])
        dur = int(event["dur"])
        pinfo = processes[pid]
        pinfo.log(tid, ts, dur, name)
    
    
    print "Start: %u" % min_ts
    print "End: %u" % max_ts
    print "Duration: %u" % (max_ts - min_ts)

#--------------------------------------------------------------------#

def main():
    if len(sys.argv) < 2:
        print "Usage: %s <gpu_trace_file> [output_dir]" % os.path.basename(sys.argv[0])
        sys.exit(1)
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else None
    analyzeTrace(sys.argv[1], output_dir)

#--------------------------------------------------------------------#

if __name__ == '__main__':
    main()
