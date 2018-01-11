#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import time
from xml.dom import minidom
from xml.etree import cElementTree as etree
from Actions.Util import log, error
from DocumentControl import DocumentControl
from EZRandomWidget import *
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from Actions.Common import *
from Actions.TFCnnBenchmarks import TFCnnBenchmarksStep
from Step import Step

def create_combo_widget(parent, list, default_value_index):
    new_combo = QComboBox(parent)
    for current_item in list:
        new_combo.addItem(current_item)
    new_combo.setCurrentIndex(default_value_index)
    return new_combo

#########
# Custom:
##########

class TMTeplatesWidget(QWidget):
    def __init__(self, values, parent = None):
        super(TMTeplatesWidget, self).__init__(parent)
        self._values = values
        self._initGui()

    def _initGui(self):
        self.setLayout(QGridLayout())
        self.cb_mode = create_combo_widget(self, ['Background','Performance', 'Nominal', 'Custom'], 0)
        self.layout().addWidget(QLabel("Mode:"), 0, 0)
        self.layout().addWidget(self.cb_mode, 0, 1)        
                
    def save(self):
        self._values["Mode"] = self.cb_mode.currentText()

#############################################################################
# General        
#############################################################################
       
         
# Using a QRunnable
# http://qt-project.org/doc/latest/qthreadpool.html
# Note that a QRunnable isn't a subclass of QObject and therefore does
# not provide signals and slots.
class RunTestSequenceThread(QThread):

    def __init__(self, owner):
        super(RunTestSequenceThread, self).__init__()
        self._owner = owner
        
    def run(self):
        self._owner._runSequence()

#############################################################################

class TestDataItem(object):

    def __init__(self, name):
        self._name = name
        self._widget = None

    #--------------------------------------------------------------------#

    def name(self):
        return self._name
    
    #--------------------------------------------------------------------#
    
    def getWidget(self):
        return self._widget
    
    #--------------------------------------------------------------------#
    
    def createWidget(self):
        return self._widget

#############################################################################

class TestDataStepList(TestDataItem):
    
    def __init__(self, on_step_select):
        super(TestDataStepList, self).__init__("Steps")
        
        self._on_step_select = on_step_select
        self._steps = {}
        self._widget = QListWidget()
        self._widget.itemSelectionChanged.connect(self._setSelectedStep)
        
    #--------------------------------------------------------------------#
    
    def _setSelectedStep(self):
        selected_items = self._widget.selectedItems()
        if selected_items is None:
            return

        step_class = self._steps[str(selected_items[0].text())]  
        step = step_class()
        self._on_step_select(step)
 
    #--------------------------------------------------------------------#
    
    def addStep(self, step_class):
        self._widget.addItem(QListWidgetItem(step_class.NAME))
        self._steps[step_class.NAME] = step_class
#         
#     #--------------------------------------------------------------------#
#     
#     def writeToXml(self, parent_node):
#         new_node = etree.SubElement(parent_node, "Attribute", Name = self._name)
#         mode_node = etree.SubElement(step_node, "Mode")
#         mode_node = EZRandomWidget.MODE_NAMES[self._widget.getMode()]
#         basic_node = etree.SubElement(step_node, "Basic")
#         basic_node.text = self._widget.getBasicText()
#         advanced_node = etree.SubElement(step_node, "Advanced")
#         advanced_node.text = self._widget.getAdvancedText()
#         return new_node    
        
#############################################################################

class TestDataAttribute(TestDataItem):
    
    def __init__(self, name, enum, default_value, allow_advanced_mode = False, base_widget_creator = None):
        
        super(TestDataAttribute, self).__init__(name)
 
        if enum == None:
            enums = None
        else:
            enums = [enum]
        
        self._widget = EZRandomWidget(allow_advanced_mode = allow_advanced_mode, base_widget_creator = base_widget_creator, parent = None, enums = enums)
        self._refreshWidget(default_value)
        
    #--------------------------------------------------------------------#
    
    def _refreshWidget(self, value):
        if self._widget.getMode() == EZRandomWidget.BASIC:
            self._widget.setBasicText(value)
        else:
            self._widget.setAdvancedText(value)
        self._widget.refreshDescriptor()
        
    #--------------------------------------------------------------------#
    
    def getValue(self):
        return self._widget.getDescriptor().next()
        
    #--------------------------------------------------------------------#
    
#     def writeToXml(self, parent_node):
#         new_node = etree.SubElement(parent_node, "Attribute", Name = self._name)
#         mode_node = etree.SubElement(step_node, "Mode")
#         mode_node = EZRandomWidget.MODE_NAMES[self._widget.getMode()]
#         basic_node = etree.SubElement(step_node, "Basic")
#         basic_node.text = self._widget.getBasicText()
#         advanced_node = etree.SubElement(step_node, "Advanced")
#         advanced_node.text = self._widget.getAdvancedText()
#         return new_node
    
    #--------------------------------------------------------------------#
    
#     def readFromXml(self, node):
#         for property_node in step_node.getchildren():
#             property_name = property_node.attrib["Name"]
#             property_value = property_node.attrib["Value"]
#             self._properties[property_name] = property_value
            
#############################################################################

class TestDataFolder(TestDataItem):
    
    class Widget(QWidget):
        def __init__(self, folder):
            super(TestDataFolder.Widget, self).__init__()
            self._folder = folder
            
        def folder(self):
            return self._folder
                
    #--------------------------------------------------------------------#
                    
    def __init__(self, name):
        
        super(TestDataFolder, self).__init__(name)
        self._step_list = None        
        self._attributes = []
        self._sub_folders = []
        
    #--------------------------------------------------------------------#
    
    def createWidget(self):
        self._widget = TestDataFolder.Widget(self)
        self._widget.setLayout(QVBoxLayout())
        
        if self._step_list is not None:
            step_list_widget = self._step_list.createWidget()
            self._widget.layout().addWidget(step_list_widget, 1)
            return self._widget
            
        for attribute in self._attributes:
            row = QWidget()
            row.setLayout(QHBoxLayout())
            row.layout().addWidget(QLabel(attribute.name() + ":"))
            row.layout().addWidget(attribute.createWidget(), 1)
            self._widget.layout().addWidget(row)

        if len(self._sub_folders) > 0:
            self._sub_folders_widget = QTabWidget()
            for sub_folder in self._sub_folders:
                self._sub_folders_widget.addTab(sub_folder.createWidget(), sub_folder.name())
                self._widget.layout().addWidget(self._sub_folders_widget, 1)
        else:
            self._widget.layout().addStretch(1)

        #self._widget.layout().setMargin(0)
        return self._widget
        
    #--------------------------------------------------------------------#
    
    def getSelectedSubFolder(self):
        if self._sub_folders_widget is None:
            return None
        return self._sub_folders_widget.currentWidget().folder()        
    
    #--------------------------------------------------------------------#
    
    def _addAttributeToObject(self, name, item):
        name = name.lower().replace(" ", "_")
        setattr(self, name, item)
        
    #--------------------------------------------------------------------#
    
    def setStepList(self, step_list):
        self._step_list = step_list
        self._addAttributeToObject(step_list.name(), step_list)

    #--------------------------------------------------------------------#
                 
    def getStepList(self):
        return self._step_list
                        
    #--------------------------------------------------------------------#
    
    def addAttribute(self, attribute):
        self._attributes.append(attribute)
        self._addAttributeToObject(attribute.name(), attribute)
    
    #--------------------------------------------------------------------#    

    def addSubFolder(self, sub_folder):
        self._sub_folders.append(sub_folder)
        self._addAttributeToObject(sub_folder.name(), sub_folder)
        
    #--------------------------------------------------------------------#
#         
#     def writeToXml(self, parent_node):
#         new_node = etree.SubElement(parent_node, "Folder", Name = self._name)
#         for item in self._items.values():
#             item.writeToXml(new_node)
#         return step_node
# 
#     def readFromXml(self, node):
#         for property_node in step_node.getchildren():
#             property_name = property_node.attrib["Name"]
#             property_value = property_node.attrib["Value"]
#             self._properties[property_name] = property_value
        
#############################################################################        

#############################################################################

class SequenceWidget(QWidget):
    
    refresh_item_signal = pyqtSignal(int)

    #--------------------------------------------------------------------#
            
    def __init__(self, parent = None):
        super(SequenceWidget, self).__init__(parent)
        self._doc = DocumentControl(self, "Xml file (*.xml);;Any File (*.*);;", ".")
        self._sequence = []
        self._selected_step = None
        self._initGui()

    #--------------------------------------------------------------------#
                        
    def _initGui(self):
        self.refresh_item_signal.connect(self._refreshItem)
        
        self.setLayout(QHBoxLayout())
        
        self.hook_selection = True
        self.sequence_widget = QListWidget()
        self.sequence_widget.selectionModel().selectionChanged.connect(self._sequenceStepSelected)
        self.progress_status = QListWidget()
        
        self.configuration_pane = QWidget()
        self.configuration_pane.setLayout(QVBoxLayout())
        self.configuration_pane.setObjectName("HighLevelWidget")
        self.configuration_pane.setStyleSheet("QWidget#HighLevelWidget { border:1px solid black; }")

        self.configurations_folder  = self._createFolder(None, "Configurations")
        self.steps_folder           = self._createFolder(self.configurations_folder, "Steps")
        self.settings_folder        = self._createFolder(self.configurations_folder, "Settings")        
        self.general_folder         = self._createFolder(self.settings_folder, "General")
        self.backup_folder          = self._createFolder(self.settings_folder, "Backup")
        self.sequence_folder        = self._createFolder(self.settings_folder, "Sequence")        
        self.spy_folder             = self._createFolder(self.settings_folder, "Spy")
        self.monitors_folder        = self._createFolder(self.spy_folder, "Monitors")
        self.checkers_folder        = self._createFolder(self.spy_folder, "Checkers")
        
#        self.global_steps_folder    = self._createFolder(self.steps_folder, "Global")
        self.benchmark_steps_folder = self._createFolder(self.steps_folder, "Benchmarks")

#         self.general_steps          = self._createStepsList(self.global_steps_folder)
        self.benchmark_steps        = self._createStepsList(self.benchmark_steps_folder)

        ##########
        # Steps: #
        ##########                                       
                                                #Name           #Attributes             #Perform                        #Repr                   #Widget
#         self._createStep(self.general_steps,    "Delay",        {"Duration": "1"},                                   performDelay,       reprNameAndAttributes,  DefaultAttributesWidget  )
#         self._createStep(self.general_steps,    "Pause",        None,                                                performStub,        reprNameAndAttributes,  DefaultAttributesWidget  )
#         self._createStep(self.general_steps,    "Compile TensorFlow",        None,                                   performCompileTF,   reprNameAndAttributes,  DefaultAttributesWidget  )        
        self._addStep(self.benchmark_steps, TFCnnBenchmarksStep)
        
        ##################
        # Configuration: #
        ##################                                       
        self._createAttribute(self.backup_folder,   "Do Backup", {"False": 0, "True": 1},   "True",   False,    create_combo_box) 
        self._createAttribute(self.monitors_folder, "Reg",       {"False": 0, "True": 1},   "True",   True,     create_combo_box)
        self._createAttribute(self.monitors_folder, "Monitor",   None,                      "True",   True,     create_combo_box)        
        
        ############
        # Buttons: #
        ############
        self.b_add = QPushButton("<<")
        self.b_remove = QPushButton("Remove")
        self.b_move_up = QPushButton("Move &Up")
        self.b_move_down = QPushButton("Move &Down")
        self.b_new = QPushButton("&New")
        self.b_save = QPushButton("&Save")
        self.b_load = QPushButton("&Load")
        self.b_run = QPushButton("&Run")
        
        self.b_add.clicked.connect      (self._bAddClicked)
        self.b_remove.clicked.connect   (self._removeStepFromSequence)
        self.b_new.clicked.connect      (self._new)
        self.b_save.clicked.connect     (self._saveToXml)
        self.b_load.clicked.connect     (self._loadFromXml)
        self.b_run.clicked.connect      (self._runSequenceInNewThread)
        
        #########
        # Panes:
        #########
        sequence_pane = QWidget()
        sequence_pane.setLayout(QHBoxLayout())
        sequence_pane.layout().addWidget(self.sequence_widget, 1)
                
        buttons_pane = QWidget()
        buttons_pane.setLayout(QVBoxLayout())
        buttons_pane.layout().addStretch(1)
        buttons_pane.layout().addWidget(self.b_add)
        buttons_pane.layout().addWidget(self.b_remove)
        buttons_pane.layout().addWidget(self.b_move_up)
        buttons_pane.layout().addWidget(self.b_move_down)
        buttons_pane.layout().addWidget(self.b_new)
        buttons_pane.layout().addWidget(self.b_save)
        buttons_pane.layout().addWidget(self.b_load)
        buttons_pane.layout().addWidget(self.b_run)
        buttons_pane.layout().addStretch(1)

        steps_edit_pane = QWidget()
        steps_edit_pane.setLayout(QVBoxLayout())
        configurations_folder_widget = self.configurations_folder.createWidget()
        configurations_folder_widget.layout().setMargin(0)

#         configurations_folder_widget.setObjectName("HighLevelWidget")
#         configurations_folder_widget.setStyleSheet("QWidget#HighLevelWidget { border:1px solid black; }")        

        steps_edit_pane.layout().addWidget(configurations_folder_widget, 1)
        steps_edit_pane.layout().addWidget(QLabel("Properties:"))
        steps_edit_pane.layout().addWidget(self.configuration_pane, 1)
        save_button = QPushButton("Update")
        save_button.clicked.connect(self._saveConfigurations)
        steps_edit_pane.layout().addWidget(save_button)                
        #steps_edit_pane.layout().addStretch(1)
                         
        self.layout().addWidget(sequence_pane, 3)
        self.layout().addWidget(buttons_pane, 1)
        self.layout().addWidget(steps_edit_pane, 3)
        #self.layout().addWidget(b_remove, 1, 1)

    #--------------------------------------------------------------------#
    
    def _setModified(self, value):
        self._doc.setModified(value)
    
    #--------------------------------------------------------------------#

    def _selectedSteps(self):
        current_folder = self.steps_folder
        step_list = current_folder.getStepList()
        while step_list is None:
            current_folder = current_folder.getSelectedSubFolder()
            step_list = current_folder.getStepList()
        selectedIndexes = step_list.getWidget().selectedIndexes()
        return selectedIndexes
    
    #--------------------------------------------------------------------#
         
    def _addStep(self, step_list, step_class):
        step_list.addStep(step_class)
    
    #--------------------------------------------------------------------#
    
    def _createFolder(self, parent_folder, name):
        folder = TestDataFolder(name)
        if parent_folder != None:
            parent_folder.addSubFolder(folder)
        return folder

    #--------------------------------------------------------------------#
    
    def _createAttribute(self, parent_folder, name, enum, default_value, allow_advanced_mode = False, base_widget_creator = None):
        attribute = TestDataAttribute(name, enum, default_value, allow_advanced_mode = allow_advanced_mode, base_widget_creator = base_widget_creator)
        parent_folder.addAttribute(attribute)
        return attribute
                
    #--------------------------------------------------------------------#
    
    def _addStepToSequence(self, step):
        self._sequence.append(step)
        self.sequence_widget.addItem(QListWidgetItem(str(step)))
        self.sequence_widget.setCurrentRow(len(self._sequence) - 1)
        self._setModified(True)
    
    #--------------------------------------------------------------------#
    
    def _removeStepFromSequence(self):
        self.sequence.takeItem()
        self._setModified(True)

    #--------------------------------------------------------------------#
    
    def _bAddClicked(self):
        self._addStepToSequence(self._selected_step)    

    #--------------------------------------------------------------------#

    def _clear(self):
        self.sequence_widget.clear()
        self._sequence = []
        self._setModified(True)

    #--------------------------------------------------------------------#

    def _createStepsList(self, folder):
        step_list = TestDataStepList(self._stepListStepSelected)
        folder.setStepList(step_list)
        return step_list
    
    #--------------------------------------------------------------------#
    
    def _stepListStepSelected(self, step):
        self._selected_step = step
        #widget = step.attributesWidget()
        #self._setConfigurationPane(widget)

    #--------------------------------------------------------------------#
        
    def _sequenceStepSelected(self, selected, deselected):
        if not self.hook_selection:
            return
        
        index = self.sequence_widget.currentRow()
        item = self._sequence[index]
        self._setConfigurationPane(item.attributesWidget())

    #--------------------------------------------------------------------#
    
    def _setConfigurationPane(self, widget):
        layout = self.configuration_pane.layout()
        if layout.count() > 0:
            current_widget = layout.itemAt(0).widget()
            if current_widget is widget:
                return
            
            while layout.count() > 0: 
                w = layout.itemAt(0).widget()
                layout.removeWidget(w)
                if w != None:
                    w.close()

        self.attributes_widget = widget
        layout.addWidget(widget)
        layout.addStretch(1)
        
    #--------------------------------------------------------------------#
    
    def _refreshItem(self, index):
        item = self._sequence[index]
        self.hook_selection = False
        self.sequence_widget.takeItem(index)
        self.sequence_widget.insertItem(index, str(item))
        self.sequence_widget.setCurrentRow(index)
        self.hook_selection = True
    
    #--------------------------------------------------------------------#
    
    def _emitRefreshItem(self, index):
        self.refresh_item_signal.emit(index)
    
    #--------------------------------------------------------------------#
        
    def _saveConfigurations(self):
        if self.attributes_widget != None:
            self.attributes_widget.save()
            index = self.sequence_widget.currentRow()
            self._refreshItem(index)

    #--------------------------------------------------------------------#
                
    def _reset(self):
        for index in range(len(self._sequence)):
            step = self._sequence[index]
            step.setPass(False)
            self._emitRefreshItem(index)
    
    #--------------------------------------------------------------------#
            
    def _runSequence(self):
        self._reset()
        print "Run sequence..."
        for index in range(len(self._sequence)):
            step = self._sequence[index]
            #log("+ %s:" % step.name())
            step.perform()
            step.setPass(True)
            self._emitRefreshItem(index)
        print "Done."
        
    #--------------------------------------------------------------------#
            
    def _runSequenceInNewThread(self):
        self.thread = RunTestSequenceThread(self)
        self.thread.start()

    #--------------------------------------------------------------------#
    
    def _new(self):
        self._doc.new()
        self._clear()
        self._setModified(False)        
        
    #--------------------------------------------------------------------#
            
    def _saveToXml(self):
        xml = etree.Element("root")
        sequence_xml = etree.SubElement(xml, "Sequence")
        for step in self._sequence:
            sub_element = step.writeToXml(sequence_xml)
        
        content = minidom.parseString(etree.tostring(xml)).toprettyxml() 
        self._doc.save(content)
        self._setModified(False)        

    #--------------------------------------------------------------------#
            
    def _loadFromXml(self):
        content = self._doc.load()
        if content == None:
            return
        
        self._clear()
        root_node = etree.fromstring(content)
        
        sequence_node = None
        for sub_element in root_node.getchildren():
            if sub_element.tag == "Sequence":
                sequence_node = sub_element
                break
            
        for step_node in sequence_node.getchildren():
            step = Step.loadFromXml(step_node)
            self._addStepToSequence(step)            
        
        self._setModified(False)        
        
    #--------------------------------------------------------------------#
    
    # Override:
    def closeEvent(self, evnt):
        if not self._doc.close():
            evnt.ignore()
            return
        super(SequenceWidget, self).closeEvent(evnt)
                
###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################
        
if __name__ == '__main__':
    app = QApplication([])
    prompt = SequenceWidget()
    prompt.setGeometry(200, 30, 1024, 600)
    prompt.show()
    app.exec_()
