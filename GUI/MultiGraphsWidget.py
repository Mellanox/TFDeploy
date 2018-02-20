#!/usr/bin/python
# -*- coding: utf-8 -*-
import csv
import os
import sys
from matplotlib import pyplot
import copy
from numpy.random.mtrand import np

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

class Step(object):
    def __init__(self, csv_line):
        parts = csv_line.replace(" ","").split(",")
        self.start_time = float(parts[0])
        self.id = int(parts[1])

###############################################################################

class Graph(object):
    
    TYPE_NORMAL = 0
    TYPE_RATE = 1
    TYPE_DELTA = 2
    
    def __init__(self, label, csv_path, graph_type, start_time, color, ymax=None):
        self._label = label
        self._csv_path = csv_path
        self._type = graph_type
        self._start_time = start_time
        self._color = color
        self._ymax = ymax
        self._x = []
        self._y = []
        self._readData()
        
    def _readData(self):
        i = 0
        last_val = None
        last_timestamp = None
        with open(self._csv_path, "r") as csv:
            for line in csv:
                parts = line.replace(" ","").split(",")
                try:        
                    timestamp = float(parts[0]) - self._start_time
                    val = float(parts[1])
                except:
                    print "Error on graph: %s: %u \"%s\." % (os.path.basename(self._csv_path), i, line)
                    raise
                i += 1

                if self._type == Graph.TYPE_NORMAL:
                    self._x.append(timestamp)
                    self._y.append(val)
                elif self._type == Graph.TYPE_RATE:                
                    rate = 0 if last_val is None else (val - last_val) / (timestamp - last_timestamp)
                    if rate > 1000000:
                        print "Error on graph: %s: %u \"%s\." % (os.path.basename(self._csv_path), i, line)
                        sys.exit(1)
                        
                    last_timestamp = timestamp
                    last_val = val
                    self._x.append(timestamp)
                    self._y.append(rate)
                elif self._type == Graph.TYPE_DELTA:                
                    self._x.append(timestamp - 0.01)
                    self._x.append(timestamp)
                    self._x.append(timestamp + 0.01)
                    self._y.append(0)
                    self._y.append(1)
                    self._y.append(0)    

    def plot(self, fig, host, pos):
        if host is None:
            print "HOST IS: %s" % self._label
            fig, host = pyplot.subplots()
            ax = host
        else:
            ax = host.twinx()
            ax.spines["right"].set_visible(True)
            ax.spines["right"].set_position(("axes", pos))

        ax.plot(self._x, self._y, self._color)
        if self._ymax is not None:
            ax.set_ylim(ax.get_ylim()[0], self._ymax)
        ax.set_ylabel(self._label, color=self._color)
        ax.tick_params('y', colors=self._color)
        return fig, host
        
###############################################################################

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "No graph dir specified."
        sys.exit(1)

#     fig, ax1 = pyplot.subplots()
#     t = np.arange(0.01, 10.0, 0.01)
#     s1 = np.exp(t)
#     ax1.plot(t, s1, 'b-')
#     ax1.set_xlabel('time (s)')
#     # Make the y-axis label, ticks and tick labels match the line color.
#     ax1.set_ylabel('exp', color='b')
#     ax1.tick_params('y', colors='b')
#      
#     ax2 = ax1.twinx()
#     s2 = np.sin(2 * np.pi * t)
#     ax2.plot(t, s2, 'r.')
#     ax2.set_ylabel('sin', color='r')
#     ax2.tick_params('y', colors='r')
#      
#     fig.tight_layout()
#     pyplot.show()
        
    graph_dir = sys.argv[1]
    timeline_path = os.path.join(graph_dir, "timeline.csv")
    
    with open(timeline_path, "r") as timeline:
        steps = []
        timeline.readline()
        for line in timeline:
            step = Step(line)
            steps.append(step)
    start_time = min([step.start_time for step in steps])  

    graphs = [Graph("step",    os.path.join(graph_dir, "timeline.csv"),      Graph.TYPE_DELTA, start_time, "r"),
              Graph("rdta",    os.path.join(graph_dir, "RDTA-mlx5_1:1.csv"), Graph.TYPE_RATE,  start_time, "g"),
              Graph("tdta",    os.path.join(graph_dir, "TDTA-mlx5_1:1.csv"), Graph.TYPE_RATE,  start_time, "b"),
              Graph("worker",  os.path.join(graph_dir, "UTIME-20231.csv"),   Graph.TYPE_RATE,  start_time, "c"),
              Graph("ps",      os.path.join(graph_dir, "UTIME-20591.csv"),   Graph.TYPE_RATE,  start_time, "m"),
              Graph("gpu (%)", os.path.join(graph_dir, "GPU-1.csv"),         Graph.TYPE_NORMAL,start_time, "y", ymax=300)]
    
    ####################
    # Convert to rate: #
    ####################
    host = None
    fig = None
    pos = 1.0
    for graph in graphs:
        fig, host = graph.plot(fig, host, pos)
        pos += 0.08
    fig.subplots_adjust(right=(1 - 0.08 * (len(graphs) - 2)))
 
    pyplot.xlabel("Time")
    pyplot.show()