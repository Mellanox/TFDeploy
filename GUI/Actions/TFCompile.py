#!/usr/bin/python
# -*- coding: utf-8 -*-

import tempfile
import re
import os

from Common.Log import UniBorder, title
from Common.Util import executeRemoteCommand, waitForProcesses
from TestEnvironment import TestEnvironment
from Step import Step

###############################################################################

@Step.REGISTER()
class TFCompileStep(Step):
    
    NAME = "TF Compile"
    
    ATTRIBUTE_ID_TENSORFLOW_HOME = 0
    ATTRIBUTE_ID_CONFIG_CUDA = 1
    ATTRIBUTE_ID_ADDITIONAL_FLAGS = 2
    ATTRIBUTE_ID_INSTALL_SERVERS = 3
    
    ATTRIBUTES = [["TensorFlow home", "~/tensorflow"],
                  ["CUDA", "True"],
                  ["Additional build flags", ""],
                  ["Install on servers", "12.12.12.25,12.12.12.26"]]

    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        Step.__init__(self, values)
        self._stopping = False

    # -------------------------------------------------------------------- #

    def tensorflow_home(self):
        return self._values[TFCompileStep.ATTRIBUTE_ID_TENSORFLOW_HOME]
    def config_cuda(self):
        return bool(self._values[TFCompileStep.ATTRIBUTE_ID_CONFIG_CUDA])
    def additional_flags(self):
        return self._values[TFCompileStep.ATTRIBUTE_ID_ADDITIONAL_FLAGS].split(",")
    def install_servers(self):
        return self._values[TFCompileStep.ATTRIBUTE_ID_INSTALL_SERVERS].split(",")
    
    # -------------------------------------------------------------------- #
    
    def attributesRepr(self):
        return self.tensorflow_home()
         
    # -------------------------------------------------------------------- #

    def perform(self, index):
        Step.perform(self, index)
        
        ##########
        # Build: #
        ##########
        title("Building:", UniBorder.BORDER_STYLE_SINGLE)
        config_cuda="--config=cuda" if self.config_cuda() else ""
        if self.additional_flags() == [""]:
            additional_flags = ""
        else:
            additional_flags = "--copt \"%s\"" % " ".join(self.additional_flags())
        cmd = "cd %s; rm -rf tensorflow_pkg; bazel build -c opt %s %s //tensorflow/tools/pip_package:build_pip_package" % (self.tensorflow_home(),
                                                                                                                           config_cuda,
                                                                                                                           additional_flags)
        res = self.runSeperate(cmd, 
                               title = "Build %s" % self.tensorflow_home(), 
                               log_file_path = os.path.join(self._logs_dir, "build.log"),
                               wait_timeout = 3600)
        if not res:
            return False
    
        cmd = "cd %s; bazel-bin/tensorflow/tools/pip_package/build_pip_package tensorflow_pkg" % (self.tensorflow_home())
        res = self.runInline(cmd, wait_timeout=60)
        if not res:
            return False

        ############
        # Install: #
        ############
        servers = TestEnvironment.Get().getServers(self.install_servers())
        title("Installing:", UniBorder.BORDER_STYLE_SINGLE)
        src_dir = os.path.join(self.tensorflow_home(), "tensorflow_pkg")
        temp_dir_name = "tmp." + next(tempfile._get_candidate_names()) + next(tempfile._get_candidate_names())
        temp_dir = os.path.join(tempfile._get_default_tempdir(), temp_dir_name)
        res = self.runSCP(servers, [src_dir], temp_dir, wait_timeout=10)
        if not res:
            return False
    
        cmd = "pip install --user --upgrade %s/tensorflow-*" % temp_dir
        process_title = lambda process: "Installing on %s..." % process.server
        log_file_path = lambda process: os.path.join(self._logs_dir, "install_%s.log" % re.sub("[^0-9a-zA-Z]", "_", process.server))
        res = self.runSeperate(cmd,
                               title = process_title,
                               servers = servers,
                               log_file_path = log_file_path)
        if not res:
            return False

        ##########
        # Clean: #
        ##########
        title("Cleaning:", UniBorder.BORDER_STYLE_SINGLE)
        processes = executeRemoteCommand(servers, "rm -rf %s" % temp_dir)
        res = waitForProcesses(processes, wait_timeout=10)
        if not res:
            return False
        return True

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
    TestEnvironment.Get().setTestLogsDir("/tmp/test_logs")
    step = TFCompileStep()
    step.perform(0)

