#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import re
import sys

def analyzeNvperf(input_path, output_dir):
    total_percent = 0.0
    total_time = 0.0
    
    with open(input_path) as f:
        for line in f:
            line = line.strip()
            if "API calls:" in line:
                break
            
            #m = re.match("^ *[0-9.]*% *[0-9.][umn]s .*", line)
            m = re.match("^.* +([0-9.]*)% *([0-9.]*)([umn]*s)", line)
            if m:
                percent = float(m.group(1))
                time = float(m.group(2))
                if m.group(3) == "ms":
                    time /= 1000.0
                elif m.group(3) == "us":
                    time /= 1000000.0
                total_percent += percent
                total_time += time
                print "%lf%% %lfs" % (percent, time)
    
    print "%lf%%" % total_percent
    print "%lfs" % total_time 

#--------------------------------------------------------------------#

def main():
    if len(sys.argv) < 2:
        print "Usage: %s <gpu_trace_file> [output_dir]" % os.path.basename(sys.argv[0])
        sys.exit(1)
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else None
    analyzeNvperf(sys.argv[1], output_dir)

#--------------------------------------------------------------------#

if __name__ == '__main__':
    main()