#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import os
from xml.dom import minidom
from xml.etree import cElementTree as etree
from Actions.Log import LOG_LEVEL_INFO, LOG_LEVEL_ERROR, setLogOps,\
    setMainProcess, getMainProcess
from DocumentControl import DocumentControl
from EZRandomWidget import *
from MultiLogWidget import MultiLogWidget
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from Actions.Common import *
from Actions.TFCnnBenchmarks import TFCnnBenchmarksStep
from Actions.Step import Step
from Actions.TestEnvironment import TestEnvironment
from Actions.TFCompile import TFCompileStep
from Actions.Util import BasicProcess

def create_combo_widget(parent, list, default_value_index):
    new_combo = QComboBox(parent)
    for current_item in list:
        new_combo.addItem(current_item)
    new_combo.setCurrentIndex(default_value_index)
    return new_combo

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
    
    #--------------------------------------------------------------------#
    
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

        self._value_widget = EZRandomWidget(allow_advanced_mode = allow_advanced_mode, base_widget_creator = base_widget_creator, parent = None, enums = enums)
        self._widget = QWidget()
        self._widget.setLayout(QHBoxLayout())
        self._widget.layout().addWidget(QLabel(self._name + ":"))
        self._widget.layout().addWidget(self._value_widget, 1)
        
        self._refreshWidget(default_value)
        
    #--------------------------------------------------------------------#
    
    def _refreshWidget(self, value):
        if self._value_widget.getMode() == EZRandomWidget.BASIC:
            self._value_widget.setBasicText(value)
        else:
            self._value_widget.setAdvancedText(value)
        self._value_widget.refreshDescriptor()
        
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

class MultiVariableWidget(QWidget):
    
    def __init__(self, parent = None):
        super(MultiVariableWidget, self).__init__(parent)
        self._values = {}
        self._initGui()
        
    
    # -------------------------------------------------------------------- #
    
    def _addVariable(self, key, value):
        row = len(self._values)
        b_remove = QPushButton("X")
        b_remove.setMaximumSize(30, 26)
        le_key = QLineEdit(key)
        le_value = QLineEdit(value)
        self.layout().addWidget(b_remove, row, 0)
        self.layout().addWidget(le_key, row, 1)
        self.layout().addWidget(le_value, row, 2)
        
    # -------------------------------------------------------------------- #
    
    def _initGui(self):
        self.setLayout(QGridLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self._addVariable(None, None)
                    
#############################################################################

class VariablesAttribute(TestDataItem):
    
    def __init__(self, name):
        super(VariablesAttribute, self).__init__(name)
        self._widget = MultiVariableWidget()
    
        
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
            attribute_widget = attribute.createWidget()
            self._widget.layout().addWidget(attribute_widget)

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
# 
# class VariableWidget(QWidget):
# 
#     def __init__(self, parent = None):
#         super(VariableWidget, self).__init__(parent)
#         self._initGui()
#         self._values = {}
#     
#     # -------------------------------------------------------------------- #
#     
#     def _initGui(self):
#         self.setLayout(Q)

#############################################################################

class ServerInfo(object):
    def __init__(self, name, ips):
        self._name = name
        self._ips = ips
        
#############################################################################

class SequenceWidget(QMainWindow):
    
    log_signal = pyqtSignal(str, object, int)
    open_log_signal = pyqtSignal(object)
    close_log_signal = pyqtSignal(object)
    refresh_item_signal = pyqtSignal(int)
    run_sequence_done_signal = pyqtSignal()

    #--------------------------------------------------------------------#
            
    def __init__(self, parent = None):
        super(SequenceWidget, self).__init__(parent)
        self._doc = DocumentControl(self, "ML tester", "Xml file (*.xml);;Any File (*.*);;", ".")
        self._sequence = []
        self._selected_step = None
        self._base_logs_dir = "test_logs"
        self._test_logs_dir = None
        self._step_logs_dir = None
        self._initGui()

    #--------------------------------------------------------------------#
                        
    def _initGui(self):
        self.setWindowIcon(QIcon("/usr/share/icons/Humanity/categories/16/applications-development.svg"))
        self.log_signal.connect(self._log)
        self.open_log_signal.connect(self._openLog)
        self.close_log_signal.connect(self._closeLog)
        self.refresh_item_signal.connect(self._refreshItem)
        self.run_sequence_done_signal.connect(self._runSequenceDone)
        
        self.hook_selection = True
        self.sequence_widget = QListWidget()
        self.sequence_widget.selectionModel().selectionChanged.connect(self._sequenceStepSelected)
#        self.sequence_widget.setRowCount(0)
#        self.sequence_widget.setColumnCount(3)
#        self.sequence_widget.setHorizontalHeaderLabels(["Step", "Name", "Attributes"])
#        self.sequence_widget.horizontalHeader().setResizeMode(0, QHeaderView.ResizeToContents)
#        self.sequence_widget.horizontalHeader().setResizeMode(1, QHeaderView.ResizeToContents)
#        self.sequence_widget.horizontalHeader().setResizeMode(2, QHeaderView.Stretch)
#        self.sequence_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.progress_status = QListWidget()
        
        self.configuration_pane = QWidget()
        self.configuration_pane.setLayout(QVBoxLayout())
        self.configuration_pane.setObjectName("HighLevelWidget")
        self.configuration_pane.setStyleSheet("QWidget#HighLevelWidget { border:1px solid black; }")
        
        self._attributes_widget = QWidget()
        self.configuration_pane.layout().addWidget(self._attributes_widget, 0)

        self.configurations_folder  = self._createFolder(None, "Configurations")
        self.steps_folder           = self._createFolder(self.configurations_folder, "Steps")
        self.settings_folder        = self._createFolder(self.configurations_folder, "Settings")
        self.variables_folder       = self._createFolder(self.configurations_folder, "Variables")
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

#         self._createAttribute(self.variables_folder, 
        ##########
        # Steps: #
        ##########                                       
                                                #Name           #Attributes             #Perform                        #Repr                   #Widget
#         self._createStep(self.general_steps,    "Delay",        {"Duration": "1"},                                   performDelay,       reprNameAndAttributes,  DefaultAttributesWidget  )
#         self._createStep(self.general_steps,    "Pause",        None,                                                performStub,        reprNameAndAttributes,  DefaultAttributesWidget  )
#         self._createStep(self.general_steps,    "Compile TensorFlow",        None,                                   performCompileTF,   reprNameAndAttributes,  DefaultAttributesWidget  )
        self._addStep(self.benchmark_steps, TFCompileStep)        
        self._addStep(self.benchmark_steps, TFCnnBenchmarksStep)
        
        ##################
        # Configuration: #
        ##################                                       
        self._createAttribute(self.backup_folder,   "Do Backup", {"False": 0, "True": 1},   "True",   False,    create_combo_box) 
        self._createAttribute(self.monitors_folder, "Reg",       {"False": 0, "True": 1},   "True",   True,     create_combo_box)
        self._createAttribute(self.monitors_folder, "Monitor",   None,                      "True",   True,     create_combo_box)        
        
        attribute = VariablesAttribute("Variables")
        self.variables_folder.addAttribute(attribute)
        
        ############
        # Buttons: #
        ############
        self.b_add = QPushButton("Add")
        self.b_remove = QPushButton("-")
        self.b_move_up = QPushButton("^")
        self.b_move_down = QPushButton("v")
        self.b_run = QPushButton("Run")
        
        self.b_add.clicked.connect      (self._bAddClicked)
        self.b_remove.clicked.connect   (self._removeStepFromSequence)
        self.b_move_up.clicked.connect  (self._moveUpInSequence)
        self.b_move_down.clicked.connect(self._moveDownInSequence)
        self.b_run.clicked.connect      (self._run)
        
        #########
        # Menus:
        #########
        newAction = QAction(QIcon('new.png'), '&New', self)
        newAction.setShortcut('Ctrl+N')
        newAction.setStatusTip('New test')
        newAction.triggered.connect(self._newAction)

        openAction = QAction(QIcon('open.png'), '&Open...', self)
        openAction.setShortcut('Ctrl+O')
        openAction.setStatusTip('Open test...')
        openAction.triggered.connect(self._loadAction)

        saveAction = QAction(QIcon('save.png'), '&Save', self)
        saveAction.setShortcut('Ctrl+S')
        saveAction.setStatusTip('Save test')
        saveAction.triggered.connect(self._saveAction)

        saveAsAction = QAction(QIcon('save_as.png'), 'Save &As...', self)
        saveAsAction.setStatusTip('Save test as...')
        saveAsAction.triggered.connect(self._saveAsAction)

        exitAction = QAction(QIcon('exit.png'), '&Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(qApp.quit)
                        
        fileMenu = self.menuBar().addMenu("&File");
        fileMenu.addAction(newAction);
        fileMenu.addAction(openAction);
        fileMenu.addAction(saveAction);        
        fileMenu.addAction(saveAsAction);
        fileMenu.addSeparator();
        fileMenu.addAction(exitAction);
        
        #########
        # Panes:
        #########
        sequence_pane = QWidget()
        sequence_pane.setLayout(QVBoxLayout())
        sequence_pane.layout().addWidget(self.sequence_widget, 1)
        sequence_buttons_pane = QWidget()
        sequence_buttons_pane.setLayout(QHBoxLayout())
        sequence_buttons_pane.layout().addWidget(self.b_run)
        sequence_buttons_pane.layout().addWidget(self.b_remove)
        sequence_buttons_pane.layout().addWidget(self.b_move_up)
        sequence_buttons_pane.layout().addWidget(self.b_move_down)
        sequence_pane.layout().addWidget(sequence_buttons_pane)

        configurations_folder_widget = self.configurations_folder.createWidget()
        configurations_folder_widget.layout().setMargin(0)

        steps_select_pane = QWidget()
        steps_select_pane.setLayout(QVBoxLayout())
        steps_select_pane.layout().setMargin(0)
        steps_select_pane.layout().addWidget(configurations_folder_widget)
        steps_select_pane.layout().addWidget(self.b_add)
        self._log_widget = MultiLogWidget()
        
        logs_pane = QWidget()
        logs_pane.setLayout(QVBoxLayout())
        logs_pane.layout().addWidget(self._log_widget)
        
#         configurations_folder_widget.setObjectName("HighLevelWidget")
#         configurations_folder_widget.setStyleSheet("QWidget#HighLevelWidget { border:1px solid black; }")        

        self.edit_pane = QWidget()
        self.edit_pane.setLayout(QVBoxLayout())
        self.edit_pane.layout().addWidget(steps_select_pane, 1)
        self.edit_pane.layout().addWidget(QLabel("Properties:"))
        self.edit_pane.layout().addWidget(self.configuration_pane, 1)

        central_widget = QWidget()
        central_widget.setLayout(QHBoxLayout())
        central_widget.layout().addWidget(sequence_pane, 2)
        central_widget.layout().addWidget(logs_pane, 5)
        central_widget.layout().addWidget(self.edit_pane, 2)

        self.setCentralWidget(central_widget)
        #self.layout().addWidget(b_remove, 1, 1)

    #--------------------------------------------------------------------#

    def _log(self, line, process, log_level):
        if process is None:
            print line
            return

        process.log(line, log_level)
        self._log_widget.log(line, process, log_level)

    #--------------------------------------------------------------------#

    def _openLog(self, process):
        process.openLog()
        self._log_widget.open(process, str(process.title))

    #--------------------------------------------------------------------#

    def _closeLog(self, process):
        process.closeLog()
        self._log_widget.close(process)
                            
    #--------------------------------------------------------------------#
    
    def emitLog(self, line, process, log_level):
        self.log_signal.emit(line, process, log_level)

    #--------------------------------------------------------------------#
    
    def emitOpenLog(self, process):
        self.open_log_signal.emit(process)

    #--------------------------------------------------------------------#
    
    def emitCloseLog(self, process):
        self.close_log_signal.emit(process)

    #--------------------------------------------------------------------#
    
    def _emitRunSequenceDone(self):
        self.run_sequence_done_signal.emit()
                   
    # -------------------------------------------------------------------- #
    
    def logOp(self, msg, process, log_level):
        self.emitLog(msg, process, log_level)

    # -------------------------------------------------------------------- #
    
    def logToMain(self, msg):
        self.emitLog(msg, getMainProcess(), LOG_LEVEL_INFO)

    # -------------------------------------------------------------------- #
    
    def errorToMain(self, msg):
        self.emitError(msg, getMainProcess(), LOG_LEVEL_INFO)

    #--------------------------------------------------------------------#
    
    def _onNewProcess(self, process):
        self.emitOpenLog(process)
        
    #--------------------------------------------------------------------#
    
    def _onProcessDone(self, process):
        if process.instance.returncode in [0, 143]:
            self.emitCloseLog(process)
            return True
        return False
        
    #--------------------------------------------------------------------#
    
    def setTestEnvironment(self):
        TestEnvironment.setOnNewProcess(self._onNewProcess)
        TestEnvironment.setOnProcessDone(self._onProcessDone)
        setLogOps(self.logOp, self.logOp)

    #--------------------------------------------------------------------#
    
    def _setModified(self):
        self._doc.setModified(True)
    
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
#    
#    def _addSequenceCell(self, r, c, data):                
#        item = TableDataItem(data)
#        item.setFlags(item.flags() ^ Qt.ItemIsEditable)
#        self.sequence_widget.setItem(r, c, item)
#        
    #--------------------------------------------------------------------#
    
    def _addStepToSequence(self, step):
        self._sequence.append(step)
        self.sequence_widget.addItem(QListWidgetItem(str(step)))
#        n = self.sequence_widget.rowCount()
#        self.sequence_widget.insertRow(n)
#        self._addSequenceCell(n, 0, step.status())
#        self._addSequenceCell(n, 1, step.name())
#        self._addSequenceCell(n, 2, step.attributesRepr())
        
    #--------------------------------------------------------------------#
    
    def _moveUpInSequence(self):
        self._moveInSequence(-1)
        
    #--------------------------------------------------------------------#
    
    def _moveDownInSequence(self):
        self._moveInSequence(1)
    
    #--------------------------------------------------------------------#
    
    def _moveInSequence(self, delta):
        index = self.sequence_widget.currentRow()
        new_index = index + delta
        if new_index < 0:
            new_index = 0
        if new_index >= self.sequence_widget.count():
            new_index = self.sequence_widget.count() - 1
        if new_index == index:
            return
        
        step = self._sequence.pop(index)
        self._sequence.insert(new_index, step)
        item = self.sequence_widget.takeItem(index)
        self.sequence_widget.insertItem(new_index, item)
        self.sequence_widget.setCurrentRow(new_index)
                
    #--------------------------------------------------------------------#
    
    def _removeStepFromSequence(self):
        index = self.sequence_widget.currentRow()
        self.sequence_widget.takeItem(index)
        self._sequence.pop(index)

    #--------------------------------------------------------------------#
    
    def _bAddClicked(self):
        if self._selected_step is None:
            return
        self._addStepToSequence(self._selected_step)
        self._setModified()

    #--------------------------------------------------------------------#

    def _clear(self):
        self.sequence_widget.clear()
        self._sequence = []

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
        widget_exists = False
        for i in range(layout.count()):
            if widget == layout.itemAt(i).widget():
                widget_exists = True
                break
        
        if not widget_exists:
            widget.bindTextChanged(self._onAttributeChanged)
            layout.addWidget(widget)
            layout.addStretch(1) 

        self._attributes_widget.hide()
        self._attributes_widget = widget
        self._attributes_widget.show()
    
    #--------------------------------------------------------------------#
    
    def _onAttributeChanged(self, attribute_index):
        def op(text):
            self._attributes_widget._values[attribute_index] = text 
            step_index = self.sequence_widget.currentRow()
            self._refreshItem(step_index)
            self._setModified()
        return op
    
    #--------------------------------------------------------------------#
    
    def _refreshItem(self, index):
        step = self._sequence[index]
        text = str(step)
        if step.status() is not None:
            text += " - " + step.status()
        self.hook_selection = False
        self.sequence_widget.takeItem(index)
        self.sequence_widget.insertItem(index, text)
        self.sequence_widget.setCurrentRow(index)
        self.hook_selection = True
    
    #--------------------------------------------------------------------#
    
    def _emitRefreshItem(self, index):
        self.refresh_item_signal.emit(index)

    #--------------------------------------------------------------------#
    
    def _setStepStatus(self, step, index, status):
        step.setStatus(status)
        self._emitRefreshItem(index)

    #--------------------------------------------------------------------#
                
    def _reset(self):
        for index in range(len(self._sequence)):
            step = self._sequence[index]
            self._setStepStatus(step, index, None)
    
    #--------------------------------------------------------------------#
    
    def _setTestLogsDir(self):
        test_name = re.sub("[^0-9a-zA-Z]", "_", os.path.basename(self._doc.filePath()))
        time_prefix = time.strftime("%Y_%m_%d_%H_%M_%S")
        self._test_logs_dir = os.path.join(self._base_logs_dir, time_prefix + "_" + test_name)
        os.makedirs(self._test_logs_dir)
        
    #--------------------------------------------------------------------#
    
    def _setStepLogsDir(self, step, index):
        step_name = re.sub("[^0-9a-zA-Z]", "_", str(step))
        self._step_logs_dir = os.path.join(self._test_logs_dir, "step_%u_%s" % (index, step_name))
        os.makedirs(self._step_logs_dir)
        TestEnvironment.setLogsFolder(self._step_logs_dir)
        
    #--------------------------------------------------------------------#
    
    def _runStep(self, index):
        step = self._sequence[index]
        self._setStepStatus(step, index, "Running...")
        self.logToMain("<h2>Step %u - %s</h2>" % (index, str(step)))
        self._setStepLogsDir(step, index)
        res = step.perform()
        if res:
            self._setStepStatus(step, index, "Passed.")
        else:
            self._setStepStatus(step, index, "Failed.")
            if step.stopOnFailure():
                return False
        return True
                                    
    #--------------------------------------------------------------------#
            
    def _runSequence(self):
        self._reset()
        self.logToMain("Run sequence...")
        for index in range(len(self._sequence)):
            if not self._runStep(index):
                break
        self.logToMain("Done.")
        self._emitRunSequenceDone()
        
    #--------------------------------------------------------------------#
            
    def _runSequenceInNewThread(self):
        self.thread = RunTestSequenceThread(self)
        self.thread.start()
        
    #--------------------------------------------------------------------#
    
    def _runSequenceDone(self):
        self.sequence_widget.setEnabled(True)
        self.edit_pane.show()
        getMainProcess().closeLog()
        setMainProcess(None)

    #--------------------------------------------------------------------#
    
    def _run(self):
        self._saveAction(True)
        self.sequence_widget.setEnabled(False)
        self.edit_pane.hide()
        self._setTestLogsDir()
        main_process = BasicProcess(None, "Running: %s" % self._doc.filePath(), os.path.join(self._test_logs_dir, "main.log"), None)
        self._openLog(main_process)
        setMainProcess(main_process)
        self._runSequenceInNewThread()

    #--------------------------------------------------------------------#
    
    def _newAction(self):
        self._doc.new()
        self._clear()
        
    #--------------------------------------------------------------------#
    
    def _getXmlContent(self):
        xml = etree.Element("root")
        sequence_xml = etree.SubElement(xml, "Sequence")
        for step in self._sequence:
            sub_element = step.writeToXml(sequence_xml)
        content = minidom.parseString(etree.tostring(xml)).toprettyxml()
        return content 
         
    #--------------------------------------------------------------------#
            
    def _saveAction(self, is_checked):
        content = self._getXmlContent()
        self._doc.save(content)

    #--------------------------------------------------------------------#
    
    def _saveAsAction(self, is_checked):
        content = self._getXmlContent()
        self._doc.saveAs(content)
        
    #--------------------------------------------------------------------#
            
    def _loadFromXml(self, file_path=None):
        content = self._doc.load(file_path)
        if content == None:
            return
        
        self._loadFromContent(content)

    #--------------------------------------------------------------------#
    
    def _loadAction(self, is_checked):
        self._loadFromXml(None)
        
    #--------------------------------------------------------------------#
            
    def loadFromXml(self, file_path=None):
        self._loadFromXml(file_path)
                
    #--------------------------------------------------------------------#
    
    def _loadFromContent(self, content):
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
            
    #--------------------------------------------------------------------#
    
    def run(self):
        self._run()
        self.thread.wait()
        
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

def _onNewProcess(process):
    process.openLog()
    
#--------------------------------------------------------------------#

def _onProcessDone(process):    
    process.closeLog()
    return process.instance.returncode in [0, 143]    

#--------------------------------------------------------------------#
        
if __name__ == '__main__':
    
    arg_parser = argparse.ArgumentParser(description = "Yaml Utils")
    arg_parser.add_argument("xml", nargs="?", help="A test file to load.")
    arg_parser.add_argument("-a", "--autorun", action="store_true", help="Automatic regression run (no GUI).")
    
    args = arg_parser.parse_args()
    app = QApplication([])    
    prompt = SequenceWidget()
    if args.xml is not None:
        prompt.loadFromXml(args.xml)
    
    if args.autorun:
        TestEnvironment.setOnNewProcess(_onNewProcess)
        TestEnvironment.setOnProcessDone(_onProcessDone)
        prompt.run()
    else:
        prompt.setTestEnvironment()
        prompt.loadFromXml("samples/performance_regression_lab.xml")
        prompt.setGeometry(200, 30, 1600, 600)
        #prompt.showMaximized()
        prompt.show()
        app.exec_()
