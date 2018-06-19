#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
from xml.dom import minidom
from xml.etree import cElementTree as etree

from test_environment import TestEnvironment
from commonpylib.gui import DefaultAttributesWidget
from commonpylib.log import log, error
from commonpylib.util import executeCommand, executeRemoteCommand, checkRetCode, remoteCopy, waitForProcesses, BasicProcess, toFileName, \
                             AttributesList

###############################################################################
    
class Step(object):
    
    STATUS_IDLE = 0
    STATUS_RUNNING = 1
    STATUS_PASSED = 2
    STATUS_FAILED = 3
    
    ATTRIBUTES = []
    WIDGET_CLASS = DefaultAttributesWidget
    
    REGISTERED_STEPS = {}
    
    @classmethod
    def REGISTER(cls):
        def _register(stepclass):
            cls.REGISTERED_STEPS[stepclass.NAME] = stepclass
            # print "REGISTERING '%s'" % stepclass.NAME
            return stepclass 
        return _register     
        
    @classmethod
    def GET_WIDGET(cls):
        return cls.WIDGET_CLASS(cls.ATTRIBUTES)
    
    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        self._name = self.className()
        self._attributes = AttributesList(type(self).ATTRIBUTES)
        if values is not None:
            for i in range(len(values)):
                self._attributes[i].val = values[i]
                
        self._status = Step.STATUS_IDLE
        self._widget = None
        self._logs_dir = None
        self._repeat = 1
        self._is_enabled = True
        self._stop = False
    
    # -------------------------------------------------------------------- #
        
    def __getattr__(self, name):
        return self._attributes.__getattr__(name)

    # -------------------------------------------------------------------- #
    
    def setLogsDir(self, index):
        dir_name = "step_%u_%s" % (index, toFileName(self.__repr__()))
        self._logs_dir = os.path.join(TestEnvironment.Get().testLogsDir(), dir_name)
        if not os.path.isdir(self._logs_dir):
            os.makedirs(self._logs_dir)
        log("Logs dir: " + self._logs_dir)
#         link_path = os.path.join(TestEnvironment.Get().testLogsDir(), "step_%u" % index)
#         if os.path.isfile(link_path):
#             os.remove(link_path)
#         os.symlink(dir_name, link_path)
    
    # -------------------------------------------------------------------- #
    
    def logsDir(self):
        return self._logs_dir
    
    # -------------------------------------------------------------------- #
    
    def setName(self, value):
        self._name = value
        
    # -------------------------------------------------------------------- #
    
    def name(self):
        return self._name
    
    # -------------------------------------------------------------------- #
    
    def setStatus(self, value):
        self._status = value
    
    # -------------------------------------------------------------------- #
    
    def status(self):
        return self._status
 
    # -------------------------------------------------------------------- #
        
    def className(self):
        return type(self).NAME

    # -------------------------------------------------------------------- #
    
    def attributes(self):
        return self._attributes
    
    # -------------------------------------------------------------------- #

    def clone(self):
        res = type(self)()
        res._name = self._name
        res._repeat = self._repeat
        res._is_enabled = self._is_enabled
        res._attributes = self._attributes.clone()
        return res

    # -------------------------------------------------------------------- #
    
    def perform(self, index):
        self.setLogsDir(index)
        self._stop = False

    # -------------------------------------------------------------------- #

    def stop(self):
        self._stop = True
        
    # -------------------------------------------------------------------- #
    
    def stopOnFailure(self):
        return True

    # -------------------------------------------------------------------- #
    
    def repeat(self):
        return self._repeat
    
    # -------------------------------------------------------------------- #
    
    def setRepeat(self, val):
        self._repeat = val
    
    # -------------------------------------------------------------------- #
    
    def isEnabled(self):
        return self._is_enabled
    
    # -------------------------------------------------------------------- #
    
    def setEnabled(self, val):
        self._is_enabled = bool(val)
    
    # -------------------------------------------------------------------- #    
    
    @staticmethod
    def logToMainProcess(msg, process):
        log(msg, None)
    
    # -------------------------------------------------------------------- #
    
    def _runCommand(self, cmd, servers, wait_timeout, on_output, on_process_start, on_process_done, factory):
        processes = []
        if servers is None:
            processes.append(executeCommand(cmd, factory=factory))
        else:
            processes.extend(executeRemoteCommand(servers, cmd, factory=factory))
        return waitForProcesses(processes,
                                wait_timeout=wait_timeout,
                                on_output=on_output,
                                on_process_start=on_process_start,
                                on_process_done=on_process_done)

    # -------------------------------------------------------------------- #
    
    def runInline(self, cmd, servers = None, wait_timeout = sys.maxint):
        ''' Run and output to global log '''
        return self._runCommand(cmd,
                                servers,
                                wait_timeout = wait_timeout,
                                on_output = Step.logToMainProcess,
                                on_process_start = None, 
                                on_process_done = checkRetCode,
                                factory = None)

    # -------------------------------------------------------------------- #
    
    def runSeperate(self, cmd, servers = None, title = None, log_file_path = None, wait_timeout = sys.maxint):
        ''' Run and output to process log '''
        factory = BasicProcess.getFactory(title, log_file_path)
        return self._runCommand(cmd, 
                                servers, 
                                wait_timeout,
                                on_output = log,
                                on_process_start = TestEnvironment.Get().on_new_process, 
                                on_process_done = TestEnvironment.Get().on_process_done,
                                factory = factory)
                
    # -------------------------------------------------------------------- #
    
    def runSCP(self, sources, dst_dir, src_servers = [None], dst_servers = [None], wait_timeout = sys.maxint):
        ''' Run SCP. Always inline. '''
        processes = remoteCopy(sources, dst_dir, src_servers=src_servers, dst_servers=dst_servers)
        return waitForProcesses(processes, 
                                wait_timeout = wait_timeout,
                                on_output = Step.logToMainProcess)
    
    # -------------------------------------------------------------------- #
    
    def attributesRepr(self):
        return ""
    
    # -------------------------------------------------------------------- #
    
    def __repr__(self):
        return self._name + ": " + self.attributesRepr()
        
    # -------------------------------------------------------------------- #
            
    def writeToXml(self, root_node):
        step_node = etree.SubElement(root_node, "Step", Class = self.className())
        etree.SubElement(step_node, "Name", Value = self.name())
        etree.SubElement(step_node, "Enabled", Value = str(self.isEnabled()))
        etree.SubElement(step_node, "Repeat", Value = str(self.repeat()))
        attributes_node = etree.SubElement(step_node, "Attributes")
        self._attributes.writeToXml(attributes_node)
        return step_node

    # -------------------------------------------------------------------- #
    
    @staticmethod
    def loadFromXml(step_node):
        step_class_name = step_node.attrib["Class"]
        if not step_class_name in Step.REGISTERED_STEPS:
            error("Node: %s" % minidom.parseString(etree.tostring(step_node)).toprettyxml())
            error("Invalid step name: %s" % step_class_name)
            raise
        
        step_class = Step.REGISTERED_STEPS[step_class_name]
        step = step_class() 
        for attr_node in step_node.getchildren():
            if attr_node.tag == "Name":
                step.setName(attr_node.attrib["Value"])
            elif attr_node.tag == "Enabled":
                attribute_value = attr_node.attrib["Value"] 
                if attribute_value == "True":
                    step.setEnabled(True)
                elif attribute_value == "False":
                    step.setEnabled(False)
                # else do nothing
            elif attr_node.tag == "Repeat":
                step.setRepeat(int(attr_node.attrib["Value"]))
            elif attr_node.tag == "Attributes":
                step._attributes.loadFromXml(attr_node)
                
        # Compatibility mode:
        step._attributes.loadFromXml(step_node)
        
        return step
