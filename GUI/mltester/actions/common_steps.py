#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
from random import randint

# -------------------------------------------------------------------- #

def performStub(step):
    print "Perform %s" % str(step)
    time.sleep(1)

# -------------------------------------------------------------------- #

def performSendFrames(step):
    print "Sending frames:"
    num_frames = int(step.attributes()["NumFrames"])
    for i in range(num_frames):
        max_size = int(step.attributes()["MaxSize"])
        min_size = int(step.attributes()["MinSize"])
        size = randint(min_size, max_size)
        print " + Sent frame of size %u" % size

# -------------------------------------------------------------------- #

def performDelay(step):
    duration = int(step.attributes()["Duration"])
    print "Sleep %u..." % duration
    time.sleep(duration)

# -------------------------------------------------------------------- #

def performCompileTF(step):
    print "Compiling tensorflow..."

