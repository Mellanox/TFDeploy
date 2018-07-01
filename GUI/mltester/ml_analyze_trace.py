#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import os
import sys
from commonpylib.util import toFileName

if len(sys.argv) < 2:
    print "Usage: %s <input-trace-file>" % os.path.basename(sys.argv[0])
    sys.exit(1)
    
input_file_path = sys.argv[1]

if len(sys.argv) < 3:
    output_dir_name = os.path.splitext(input_file_path)[0]
    if not os.path.exists(output_dir_name):
        os.makedirs(output_dir_name)
else:
    output_dir_name = sys.argv[2]

class ProcessInfo(object):
    def __init__(self, pname):
        self.pname = pname
        self._files = {}
    
    def _getOrCreateLog(self, tid):
        f = self._files.get(tid)
        if not f:
            file_name = "TL-" + toFileName(self.pname) + ("_%u.csv" % tid)
            file_path = os.path.join(output_dir_name, file_name)
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
    pinfo = ProcessInfo(event["args"]["name"])
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

