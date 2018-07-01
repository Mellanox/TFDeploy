'''
Created on Jun 26, 2018

@author: eladw
'''

import os
import sys
from commonpylib.monitors.measurement import StatsValue

#--------------------------------------------------------------------#

class ProcessInfo(object):
    def __init__(self, s):
        parts = s.split("/")
        self.job        = parts[1].split(":")[1]
        self.replica    = int(parts[2].split(":")[1])
        self.task       = int(parts[3].split(":")[1])
        self.device     = "-".join(parts[4].split(":")[1:2])

#--------------------------------------------------------------------#

class RequestInfo(object):
    def __init__(self, key):
        parts = key.split(";") 
        self.src = ProcessInfo(parts[0])
        self.dst = ProcessInfo(parts[2])
        self.name = parts[3]
        self.size = None
        self.start_ts = {}
        self.done_ts = {}
        self.latency = StatsValue()

#--------------------------------------------------------------------#

class TimelineSample(object):
    def __init__(self, start, end, label):
        self.start = start
        self.end = end
        self.label = label

#--------------------------------------------------------------------#

class Timeline(object):
    def __init__(self, file_path):
        self.last_ts = 0
        self.file = open(file_path, "w")

#--------------------------------------------------------------------#

class TimelineList(object):
    def __init__(self, output_dir):
        self._output_dir = output_dir
        self._file_prefix = os.path.join(output_dir, "TL_verbs_")
        self._timelines = []
    
    def _addNew(self):
        file_path = self._file_prefix + "_%03u.csv" % len(self._timelines)
        tl = Timeline(file_path)
        self._timelines.append(tl)
        print "Created a new timeline: %s" % file_path
        return tl
    
    def _find(self, start_ts):
        for tl in self._timelines:
            if start_ts >= tl.last_ts:
                return tl
        return self._addNew()
    
    def generate(self, samples):
        samples = sorted(samples, key=lambda x: x.start)
        for sample in samples:
            tl = self._find(sample.start)
            tl.file.write("%lf, 0, %s\n" % (sample.start, sample.label))
            tl.file.write("%lf, 1\n" % (sample.start))
            tl.file.write("%lf, 1\n" % (sample.end))
            tl.file.write("%lf, 0\n" % (sample.end))
            tl.last_ts = sample.end

#--------------------------------------------------------------------#

def generateTimelines(requests, output_dir):
    tls = TimelineList(output_dir)
    samples = []
    for request in requests.values():
        for key, start_ts in request.start_ts.iteritems():
            done_ts = request.done_ts[key]
            label = request.name
            samples.append(TimelineSample(start_ts, done_ts, label))
    tls.generate(samples)

#--------------------------------------------------------------------#

def generateReport(requests, output_dir):
    total_latency = 0.0
    for request in requests.values():
        num_steps = len(request.start_ts)
        if num_steps < 110:
            continue
        latency = request.latency
        total_latency += latency.avg
        print "(%3u) %-80s [%6s ==> %-6s] Size: 0x%-8x Avg: %.6f Min: %.6f Max: %.6f" % (num_steps, request.name, request.src.job, request.dst.job,
                                                                                           request.size, latency.avg, latency.min, latency.max)
    print "Total tensors: %u" % len(requests) 
    print "Total latency: %.6f" % total_latency

#--------------------------------------------------------------------#

def analyzeVerbs(requests_start_file,
                 requests_done_file,
                 output_dir = None,
                 generate_report = True,
                 generate_timelines = False):
    requests = {}
    if output_dir is None:
        output_dir = os.path.dirname(requests_start_file)
    
    with open(requests_start_file) as f:
        for line in f:
            line = line.strip()
            parts = line.split(",")
            ts = int(parts[0]) / 1000000.0
            step_id = parts[1]
            key = parts[2]
            request = requests.get(key)
            if not request:
                #print "ADDED REQUEST %s" % key 
                request = RequestInfo(key)
                requests[key] = request
            request.start_ts[step_id] = ts
    
    with open(requests_done_file) as f:
        for line in f:
            line = line.strip()
            parts = line.split(",")
            ts = int(parts[0]) / 1000000.0
            step_id = parts[1]
            key = parts[2]
            size = int(parts[3], 16)
            request = requests.get(key)
            if not request:
                print "Error at %s: request was not started." % key
                sys.exit(1)
            
            latency = ts - request.start_ts[step_id] 
            if latency <= 0:
                print "Error at %s: latency is not a positive number." % key
                sys.exit(1)
            request.done_ts[step_id] = ts
            request.latency.update(latency)
            request.size = size
    
    if generate_report:
        generateReport(requests, output_dir)
    if generate_timelines:
        generateTimelines(requests, output_dir)
