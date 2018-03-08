#!/usr/bin/python
# -*- coding: utf-8 -*-

import copy

import sys
from PyQt4.QtGui import QWidget, QGridLayout, QLineEdit, QLabel, QComboBox
from xml.dom import minidom
from xml.etree import cElementTree as etree
import re
import os

from TestEnvironment import TestEnvironment
from Common.Util import executeCommand, executeRemoteCommand, checkRetCode,\
    copyToRemote, waitForProcesses, BasicProcess, toFileName
from Common.Log import log, error, UniBorder, title
from PyQt4.Qt import QString

###############################################################################

class StepAttribute():
    def __init__(self, name, default_value, possible_values = None):
        self.name = name
        self.default_value = default_value
        self.possible_values = possible_values

###############################################################################

class DefaultAttributesWidget(QWidget):
    
    def __init__(self, attributes, parent = None):
        super(DefaultAttributesWidget, self).__init__(parent)
        self._attributes = attributes
        self._field_widgets = []
        self._field_labels = []
        self._values = None
        self._on_field_changed = []
        self._initGui()

    # -------------------------------------------------------------------- #
    
    def _initGui(self):
        self.setLayout(QGridLayout())
        for field_index in range(len(self._attributes)):
            attribute = self._attributes[field_index]
            l = QLabel(attribute.name)
            self._field_labels.append(l)
            if attribute.possible_values is None:
                w = QLineEdit()
            else:
                w = QComboBox()
                w.addItems(attribute.possible_values)
            self._field_widgets.append(w)
            self._bindField(field_index)
            self.layout().addWidget(l, field_index, 0)
            self.layout().addWidget(w, field_index, 1)

    # -------------------------------------------------------------------- #
    
    def _showField(self, field_index, val):
        if val:
            self._field_labels[field_index].show()
            self._field_widgets[field_index].show()
        else:
            self._field_labels[field_index].hide()
            self._field_widgets[field_index].hide()

    # -------------------------------------------------------------------- #
    
    def _setFieldValue(self, field_index, val):
        w = self._field_widgets[field_index]
        if isinstance(w, QLineEdit):
            w.setText(val)
        elif isinstance(w, QComboBox):
            index = w.findText(QString(str(val)))
            w.setCurrentIndex(index)
            
    # -------------------------------------------------------------------- #
    
    def _getFieldValue(self, field_index):
        w = self._field_widgets[field_index]
        if isinstance(w, QLineEdit):
            return str(w.text())
        elif isinstance(w, QComboBox):
            return str(w.currentText())
        return None
        
    # -------------------------------------------------------------------- #

    def _onFieldChanged(self, field_index, val):
#         print "ON FIELD CHANGED " + str(field_index) + " " + str(val)
        for handler in self._on_field_changed:
            handler(field_index, val)

    # -------------------------------------------------------------------- #
    
    def _bindField(self, field_index):
        w = self._field_widgets[field_index]
        op = lambda _: self._onFieldChanged(field_index, self._getFieldValue(field_index))
        if isinstance(w, QLineEdit):
            w.textChanged.connect(op)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(op)

    # -------------------------------------------------------------------- #
    
    def addFieldChangedHandler(self, handler):
        self._on_field_changed.append(handler)
    
    # -------------------------------------------------------------------- #
    
    def values(self):
        return self._values
    
    # -------------------------------------------------------------------- #

    def load(self, values):
        self._values = values 
        for field_index in range(len(self._field_widgets)):
            attr_value = self._values[field_index]
            w = self._field_widgets[field_index]
            if isinstance(w, QLineEdit): 
                w.setText(str(attr_value))
            elif isinstance(w, QComboBox):
                index = w.findText(QString(str(attr_value)))
                w.setCurrentIndex(index)
        
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
        attributes = type(self).ATTRIBUTES
        if values is None:
            values = [att.default_value for att in attributes]
        self._values = values   # The attribute values of individual step
        self._status = Step.STATUS_IDLE
        self._widget = None
        self._logs_dir = None
        self._repeat = 1
        self._is_enabled = True
        self._stop = False
    
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
    
    def values(self):
        return self._values

    # -------------------------------------------------------------------- #

    def clone(self):
        values = copy.deepcopy(self._values)
        res = type(self)(values)
        res._name = self._name
        res._repeat = self._repeat
        res._is_enabled = self._is_enabled
        return res

    # -------------------------------------------------------------------- #
    
    def attributesWidget(self, parent = None):
        if self._widget is None:
            self._widget = type(self).GET_WIDGET()
            self._widget.load(self._values)
        return self._widget

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
        return self._name + ": " + self.attributesRepr()
        
    # -------------------------------------------------------------------- #
            
    def writeToXml(self, root_node):
        attributes = type(self).ATTRIBUTES
        step_node = etree.SubElement(root_node, "Step", Class = self.className())
        etree.SubElement(step_node, "Name", Value = self.name())
        for i in range(len(attributes)):
            attr_name = attributes[i].name
            attr_value = self._values[i]
            attr_node = etree.SubElement(step_node, "Attribute", Name = attr_name, Value = str(attr_value))
        etree.SubElement(step_node, "Enabled", Value = str(self.isEnabled()))
        etree.SubElement(step_node, "Repeat", Value = str(self.repeat()))
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
        attribute_names = [attr.name for attr in step_class.ATTRIBUTES]
        step = step_class() 
        for attr_node in step_node.getchildren():
            if attr_node.tag == "Name":
                step.setName(attr_node.attrib["Value"])
            elif attr_node.tag == "Attribute":
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

if __name__ == '__main__':
    @Step.REGISTER()
    class DemoStep1(Step):
        NAME = "Demo Step 1"
        ATTRIBUTES = [StepAttribute("ATTR1", ""), 
                      StepAttribute("ATTR2", ""),
                      StepAttribute("ATTR3", "")]
    
    @Step.REGISTER()
    class DemoStep2(Step):
        NAME = "Demo Step 2"
        ATTRIBUTES = [StepAttribute("TEST1", ""), 
                      StepAttribute("TEST2", ""),
                      StepAttribute("TEST3", "")]
            
    title("Demo", UniBorder.BORDER_STYLE_STRONG)
    xml = etree.Element("root")

    step1 = DemoStep1(values=[1, 2, 3])
    step2 = DemoStep1(values=[4, 5, 6])
    step3 = DemoStep2(values=[1, 2, 3])
    step4 = DemoStep2(values=[4, 5, 6])
    
    step1.setEnabled(False)
    step1.setRepeat(20)
    step1.setName("A test step #1")
    
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
        print step.name()
        print step.isEnabled()
        print step.repeat()
