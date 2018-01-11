#!/usr/bin/python
# -*- coding: utf-8 -*-

import copy
from Actions.Util import log, error, title, UniBorder
from PyQt4.QtGui import QWidget, QGridLayout, QLineEdit, QLabel
from xml.dom import minidom
from xml.etree import cElementTree as etree
import sys

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
    
    ATTRIBUTES = []
    WIDGET = None
    WIDGET_CLASS = DefaultAttributesWidget
    
    __REGISTERED_STEPS = {}
    
    @classmethod
    def REGISTER(cls):
        def _register(stepclass):
            cls.__REGISTERED_STEPS[stepclass.NAME] = stepclass
            return stepclass 
        return _register     
        
    @classmethod
    def GET_WIDGET(cls):
        if cls.WIDGET is None:
            cls.WIDGET = cls.WIDGET_CLASS(cls.ATTRIBUTES)
        return cls.WIDGET
    
    # -------------------------------------------------------------------- #
    
    def __init__(self, values = None):
        attributes = type(self).ATTRIBUTES
        if values is None:
            values = [att[1] for att in attributes]
        self._values = values   # The attribute values of individual step
        self._pass = False  # Status
        
    # -------------------------------------------------------------------- #
    
    def setPass(self, value):
        self._pass = value
    
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
    
    def attributesWidget(self):
        widget = type(self).GET_WIDGET()
        widget.load(self._values)
        return widget

    # -------------------------------------------------------------------- #
    
    def perform(self):
        print "Empty."
        
    # -------------------------------------------------------------------- #
            
    def __repr__(self):
        s = type(self).NAME
        s += " [" + " ".join(self.values()) + "]" 
        if self._pass:
            s += " ........ Passed."
        return s
        
    # -------------------------------------------------------------------- #
            
    def writeToXml(self, root_node):
        attributes = type(self).ATTRIBUTES
        step_node = etree.SubElement(root_node, "Step", Name = type(self).NAME)
        for i in range(len(attributes)):
            attr_name = attributes[i][0]
            attr_value = self._values[i]
            attr_node = etree.SubElement(step_node, "Attribute", Name = attr_name, Value = str(attr_value))
        return step_node

    # -------------------------------------------------------------------- #
    
    @staticmethod
    def loadFromXml(step_node):
        step_name = step_node.attrib["Name"]
        if not step_name in Step.__REGISTERED_STEPS:
            error("Node: %s" % step_node)
            error("Invalid step name: %s" % step_name)
            sys.exit(1)        
        
        step_class = Step.__REGISTERED_STEPS[step_name]
        
        attribute_names = [attr[0] for attr in step_class.ATTRIBUTES]
        step = step_class() 
        for attr_node in step_node.getchildren():
            attribute_name = attr_node.attrib["Name"]
            attribute_value = attr_node.attrib["Value"]
            pos = attribute_names.index(attribute_name)
            step.values()[pos] = attribute_value
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

 

            
