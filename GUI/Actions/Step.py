#!/usr/bin/python
# -*- coding: utf-8 -*-

import copy

import sys
from PyQt4.QtGui import QWidget, QGridLayout, QLineEdit, QLabel
from xml.dom import minidom
from xml.etree import cElementTree as etree
import re
import os

from TestEnvironment import TestEnvironment
from Common.Util import executeCommand, executeRemoteCommand, checkRetCode,\
    copyToRemote, waitForProcesses, BasicProcess
from Common.Log import log, error, UniBorder, title

###############################################################################

class DefaultAttributesWidget(QWidget):
    
    def __init__(self, attributes, parent = None):
        super(DefaultAttributesWidget, self).__init__(parent)
        self._attributes = attributes
        self._line_edits = []
        self._values = None
        self._initGui()

    # -------------------------------------------------------------------- #
    
    def _initGui(self):
        self.setLayout(QGridLayout())
        for row in range(len(self._attributes)):
            attr_name = self._attributes[row][0]
            le = QLineEdit()
            self._line_edits.append(le) 
            self.layout().addWidget(QLabel(attr_name), row, 0)
            self.layout().addWidget(le, row, 1)

    # -------------------------------------------------------------------- #
    
    def bindTextChanged(self, handler):
        for row in range(len(self._line_edits)):
            le = self._line_edits[row]
            le.textChanged.connect(handler(row))
        
    # -------------------------------------------------------------------- #

    def load(self, values):
        self._values = values 
        for row in range(len(self._line_edits)):
            attr_value = self._values[row]
            self._line_edits[row].setText(str(attr_value))
        
    # -------------------------------------------------------------------- #
                    
    def save(self):
        if self._values == None:
            return
        
        for row in range(len(self._line_edits)):
            self._values[row] = str(self._line_edits[row].text())


###############################################################################
    
class Step(object):
    
    STATUS_IDLE = 0
    STATUS_RUNNING = 1
    STATUS_PASSED = 2
    STATUS_FAILED = 3
    
    ATTRIBUTES = []
    WIDGET = None
    WIDGET_CLASS = DefaultAttributesWidget
    
    __REGISTERED_STEPS = {}
    
    @classmethod
    def REGISTER(cls):
        def _register(stepclass):
            cls.__REGISTERED_STEPS[stepclass.NAME] = stepclass
            # print "REGISTERING '%s'" % stepclass.NAME
            return stepclass 
        return _register     
        
    @classmethod
    def GET_WIDGET(cls):
        return cls.WIDGET_CLASS(cls.ATTRIBUTES)
    
    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        attributes = type(self).ATTRIBUTES
        if values is None:
            values = [att[1] for att in attributes]
        self._values = values   # The attribute values of individual step
        self._status = Step.STATUS_IDLE
        self._widget = None
        self._logs_dir = None
        self._repeat = 1
        self._is_enabled = True
        self._stop = False
    
    # -------------------------------------------------------------------- #
    
    def setLogsDir(self, index):
        if self._logs_dir is None:
            self._logs_dir = os.path.join(TestEnvironment.Get().testLogsDir(),
                                          "step_%u_%s" % (index, re.sub("[^0-9a-zA-Z]", "_", self.__repr__())))
            if not os.path.isdir(self._logs_dir):
                os.makedirs(self._logs_dir)
        
    # -------------------------------------------------------------------- #
    
    def setStatus(self, value):
        self._status = value
    
    # -------------------------------------------------------------------- #
    
    def status(self):
        return self._status
    
    # -------------------------------------------------------------------- #
        
    def name(self):
        return type(self).NAME
    
    # -------------------------------------------------------------------- #
    
    def values(self):
        return self._values

    # -------------------------------------------------------------------- #

    def clone(self):
        values = copy.deepcopy(self._values)
        return type(self)(values)

    # -------------------------------------------------------------------- #
    
    def attributesWidget(self, parent = None):
        if self._widget is None:
            self._widget = type(self).GET_WIDGET()
            self._widget.load(self._values)
        return self._widget

    # -------------------------------------------------------------------- #
    
    def perform(self, index):
        raise Exception("Unimplemented perform() - step %u." % index) 

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
    
    def _runCommand(self, cmd, servers, wait_timeout, on_output, on_process_start, on_process_done, factory, verbose):
        processes = []
        if servers is None:
            processes.append(executeCommand(cmd, factory=factory, verbose=verbose))
        else:
            processes.extend(executeRemoteCommand(servers, cmd, factory=factory, verbose=verbose))
        return waitForProcesses(processes,
                                wait_timeout=wait_timeout,
                                on_output=on_output,
                                on_process_start=on_process_start,
                                on_process_done=on_process_done,
                                verbose=verbose)

    # -------------------------------------------------------------------- #
    
    def runInline(self, cmd, servers = None, wait_timeout = sys.maxint, verbose = True):
        ''' Run and output to global log '''
        return self._runCommand(cmd,
                                servers,
                                wait_timeout = wait_timeout,
                                on_output = Step.logToMainProcess,
                                on_process_start = None, 
                                on_process_done = checkRetCode,
                                factory = None,
                                verbose = verbose)

    # -------------------------------------------------------------------- #
    
    def runSeperate(self, cmd, servers = None, title = None, log_file_path = None, wait_timeout = sys.maxint, verbose = True):
        ''' Run and output to process log '''
        factory = BasicProcess.getFactory(title, log_file_path)
        return self._runCommand(cmd, 
                                servers, 
                                wait_timeout,
                                log,
                                TestEnvironment.onNewProcess(), 
                                TestEnvironment.onProcessDone(),
                                factory = factory,
                                verbose = verbose)
                
    # -------------------------------------------------------------------- #
    
    def runSCP(self, servers, sources, remote_dir, wait_timeout=None):
        ''' Run SCP. Always inline. '''
        processes = copyToRemote(servers, sources, remote_dir)
        return waitForProcesses(processes, 
                                wait_timeout=wait_timeout, 
                                on_output=log, 
                                on_error=error)
    
    # -------------------------------------------------------------------- #
    
    def attributesRepr(self):
        return ""
    
    # -------------------------------------------------------------------- #
    
    def __repr__(self):
        return self.name() + ": " + self.attributesRepr() 
        
    # -------------------------------------------------------------------- #
            
    def writeToXml(self, root_node):
        attributes = type(self).ATTRIBUTES
        step_node = etree.SubElement(root_node, "Step", Name = type(self).NAME)
        for i in range(len(attributes)):
            attr_name = attributes[i][0]
            attr_value = self._values[i]
            attr_node = etree.SubElement(step_node, "Attribute", Name = attr_name, Value = str(attr_value))
        etree.SubElement(step_node, "Enabled", Value = str(self.isEnabled()))
        etree.SubElement(step_node, "Repeat", Value = str(self.repeat()))
        return step_node

    # -------------------------------------------------------------------- #
    
    @staticmethod
    def loadFromXml(step_node):
        step_name = step_node.attrib["Name"]
        if not step_name in Step.__REGISTERED_STEPS:
            error("Node: %s" % minidom.parseString(etree.tostring(step_node)).toprettyxml())
            error("Invalid step name: %s" % step_name)
            raise
        
        step_class = Step.__REGISTERED_STEPS[step_name]
        
        attribute_names = [attr[0] for attr in step_class.ATTRIBUTES]
        step = step_class() 
        for attr_node in step_node.getchildren():
            if attr_node.tag == "Attribute":
                attribute_name = attr_node.attrib["Name"]
                attribute_value = attr_node.attrib["Value"]
                pos = attribute_names.index(attribute_name)
                step.values()[pos] = attribute_value
            elif attr_node.tag == "Enabled":
                attribute_value = attr_node.attrib["Value"] 
                if attribute_value == "True":
                    step.setEnabled(True)
                elif attribute_value == "False":
                    step.setEnabled(False)
                # else do nothing
            elif attr_node.tag == "Repeat":
                step.setRepeat(int(attr_node.attrib["Value"]))
                
        return step
            
###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

@Step.REGISTER()
class DemoStep1(Step):
    NAME = "Demo Step 1"
    ATTRIBUTES = [["ATTR1", ""], 
                  ["ATTR2", ""],
                  ["ATTR3", ""]]



###############################################################################

@Step.REGISTER()
class DemoStep2(Step):
    NAME = "Demo Step 2"
    ATTRIBUTES = [["TEST1", ""], 
                  ["TEST2", ""],
                  ["TEST3", ""]]

###############################################################################

if __name__ == '__main__':
            
    title("Demo", UniBorder.BORDER_STYLE_STRONG)
    xml = etree.Element("root")

    step1 = DemoStep1([1, 2, 3])
    step2 = DemoStep1([4, 5, 6])
    step3 = DemoStep2([1, 2, 3])
    step4 = DemoStep2([4, 5, 6])
    
    step1.setEnabled(False)
    step1.setRepeat(20)
    
    step1.writeToXml(xml)
    step2.writeToXml(xml)
    step3.writeToXml(xml)
    step4.writeToXml(xml)            

    content = minidom.parseString(etree.tostring(xml)).toprettyxml()
    print content
    
    title("Load:", UniBorder.BORDER_STYLE_SINGLE)
    root_node = etree.fromstring(content)
        
    sequence_node = None
    for step_node in root_node.getchildren():
        step = Step.loadFromXml(step_node)
        print step
        print step.isEnabled()
        print step.repeat()
