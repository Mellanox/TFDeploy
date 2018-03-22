#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
Created on Mar 22, 2018

@author: eladw
'''

import shutil
import os
from mltester.actions import TestEnvironment, TFCnnBenchmarksStep
       
###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
    if os.path.isdir("/tmp/test_logs"):
        shutil.rmtree("/tmp/test_logs")        
    TestEnvironment.Get().setTestLogsDir("/tmp/test_logs")
    step = TFCnnBenchmarksStep()
    step.perform(0)