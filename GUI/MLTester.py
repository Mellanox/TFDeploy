#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
from xml.dom import minidom
from xml.etree import cElementTree as etree
from Common.Log import LOG_LEVEL_INFO, LOG_LEVEL_ERROR, setLogOps,\
    setMainProcess, getMainProcess, LOG_LEVEL_NOTE, log, setLogLevel,\
    LOG_LEVEL_ALL, title, UniBorder
    
from DocumentControl import DocumentControl
from EZRandomWidget import *
from MultiLogWidget import MultiLogWidget
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from Actions.TFCompile import TFCompileStep
from Actions.TFCnnBenchmarks import TFCnnBenchmarksStep
from Actions.TestEnvironment import TestEnvironment
from Actions.Step import Step
import time
from Common.Util import BasicProcess
from StepEditDialog import StepEditDialog

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
        self._attributes = []
        self._sub_folders = []
        
    #--------------------------------------------------------------------#
    
    def createWidget(self):
        self._widget = TestDataFolder.Widget(self)
        self._widget.setLayout(QVBoxLayout())
            
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

class ActionWithButton(QAction):
    def __init__(self, mnt, icon_path, text, shortcut, status_tip, handler, enabled=True, checkable=False, checked=False):
        super(ActionWithButton, self).__init__(QIcon(icon_path), text, mnt.menu)
        self.setShortcut(shortcut)
        self.setStatusTip(status_tip)
        self.triggered.connect(handler)
        self.setEnabled(enabled)
        self.setCheckable(checkable)
        self.setChecked(checked)
        
        self.button = QPushButton()
        self.button.setIconSize(QSize(24,24))
        self._updateButtonStatusFromAction()
        
        self.changed.connect(self._updateButtonStatusFromAction)
        self.button.clicked.connect(self._buttonClicked)

        mnt.menu.addAction(self)
        if os.path.isfile(icon_path):
            mnt.toolbar.addWidget(self.button)
    
    # -------------------------------------------------------------------- #
    
    def _buttonClicked(self, checked):
        self.trigger()

    # -------------------------------------------------------------------- #
        
    def _updateButtonStatusFromAction(self):
        #self.button.setText        (self.text())
        self.button.setStatusTip   (self.statusTip())
        self.button.setToolTip     (self.toolTip())
        self.button.setIcon        (self.icon())
        self.button.setEnabled     (self.isEnabled())
        self.button.setCheckable   (self.isCheckable())
        self.button.setChecked     (self.isChecked())        

#############################################################################

class MenuWithToolbar(object):
    def __init__(self, parent, text):
        self.parent = parent
        self.name = text.replace("&", "")
        self.menu = parent.menuBar().addMenu(text)
        self.toolbar = QToolBar(text)
        self.parent.addToolBar(self.toolbar)
    
    #--------------------------------------------------------------------#
    
    def add(self, action_with_button):
        self.menu.addAction(action_with_button)
        self.toolbar.addWidget(action_with_button.button)

#############################################################################

class MLTester(QMainWindow):
    
    log_signal = pyqtSignal(str, object, int)
    open_log_signal = pyqtSignal(object)
    close_log_signal = pyqtSignal(object)
    refresh_item_signal = pyqtSignal(int)
    run_sequence_done_signal = pyqtSignal()

    #--------------------------------------------------------------------#
            
    def __init__(self, parent = None):
        super(MLTester, self).__init__(parent)
        self._doc = DocumentControl(self, "ML tester", "Xml file (*.xml);;Any File (*.*);;", ".")
        self._sequence = []
        self._selected_step = None
        self._base_logs_dir = "test_logs"
        self._test_logs_dir = None
        self._step_logs_dir = None
        self._current_step = None
        self._copied_steps = []
        self._error_processes = []
        self._is_running = False
        self._do_stop = False
        self._initGui()

    #--------------------------------------------------------------------#
                        
    def _initGui(self):
        
        self.setStyleSheet('''
            QPushButton { background-color: white } 
            QPushButton:hover { background-color: #cccccc }
            ''')
        self.setWindowIcon(QIcon("/usr/share/icons/Humanity/categories/16/preferences-desktop.svg"))
        self.log_signal.connect(self._log)
        self.open_log_signal.connect(self._openLog)
        self.close_log_signal.connect(self._closeLog)
        self.refresh_item_signal.connect(self._refreshItem)
        self.run_sequence_done_signal.connect(self._runSequenceDone)
        
#         self.sequence_widget = QListWidget()
        self.sequence_widget = QTableWidget()
        self.sequence_widget.setColumnCount(5)
        self.sequence_widget.setHorizontalHeaderLabels(["", "#", "", "Name", "Attributes"])
        self.sequence_widget.horizontalHeader().setResizeMode(0, QHeaderView.ResizeToContents)
        self.sequence_widget.horizontalHeader().setResizeMode(1, QHeaderView.ResizeToContents)
        self.sequence_widget.horizontalHeader().setResizeMode(2, QHeaderView.ResizeToContents)        
        self.sequence_widget.horizontalHeader().setResizeMode(3, QHeaderView.ResizeToContents)
        self.sequence_widget.horizontalHeader().setResizeMode(4, QHeaderView.Stretch)
        self.sequence_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sequence_widget.selectionModel().selectionChanged.connect(self._sequenceStepSelected)
        self.sequence_widget.itemChanged.connect(self._onSequenceItemChanged)
        self.sequence_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.configuration_pane = QWidget()
        self.configuration_pane.setLayout(QVBoxLayout())
#         self.configuration_pane.setObjectName("HighLevelWidget")
#         self.configuration_pane.setStyleSheet("QWidget#HighLevelWidget { border:1px solid black; }")
        self._attributes_widget = QWidget()
        self.configuration_pane.layout().addWidget(self._attributes_widget, 0)
        self.configuration_pane.layout().addStretch(1)

        self.configuration_box = QScrollArea()
        self.configuration_box.setWidget(self.configuration_pane)
        self.configuration_box.setWidgetResizable(True)
        self.configuration_box.setFixedHeight(400)

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

#         self._createAttribute(self.variables_folder, 
        ##########
        # Steps: #
        ##########                                       
                                                #Name           #Attributes             #Perform                        #Repr                   #Widget
#         self._createStep(self.general_steps,    "Delay",        {"Duration": "1"},                                   performDelay,       reprNameAndAttributes,  DefaultAttributesWidget  )
#         self._createStep(self.general_steps,    "Pause",        None,                                                performStub,        reprNameAndAttributes,  DefaultAttributesWidget  )
#         self._createStep(self.general_steps,    "Compile TensorFlow",        None,                                   performCompileTF,   reprNameAndAttributes,  DefaultAttributesWidget  )
        
        ##################
        # Configuration: #
        ##################                                       
        self._createAttribute(self.backup_folder,   "Do Backup", {"False": 0, "True": 1},   "True",   False,    create_combo_box) 
        self._createAttribute(self.monitors_folder, "Reg",       {"False": 0, "True": 1},   "True",   True,     create_combo_box)
        self._createAttribute(self.monitors_folder, "Monitor",   None,                      "True",   True,     create_combo_box)        
        
        attribute = VariablesAttribute("Variables")
        self.variables_folder.addAttribute(attribute)
        
        #########
        # Menus:
        #########
                          
        self.file_menu   = MenuWithToolbar(self, "&File")      
        self.edit_menu   = MenuWithToolbar(self, "&Edit")
        self.run_menu    = MenuWithToolbar(self, "&Run")
        self.window_menu = MenuWithToolbar(self, "&Window")
        self.help_menu   = MenuWithToolbar(self, "&Help")
                
        self.newAction       = ActionWithButton(self.file_menu, "images/new.jpeg",      "&New",          "Ctrl+N", "New test", self._newAction)
        self.openAction      = ActionWithButton(self.file_menu, "images/open.jpeg",     "&Open...",      "Ctrl+O", "Open test...", self._openAction)
        self.saveAction      = ActionWithButton(self.file_menu, "images/save.jpeg",     "&Save",         "Ctrl+S", "Save test", self._saveAction)
        self.saveAsAction    = ActionWithButton(self.file_menu, "images/save_as.jpeg",  "Save &As...",   "Ctrl+S", "Save test as...", self._saveAction)
        self.file_menu.menu.addSeparator()        
        self.quitAction      = ActionWithButton(self.file_menu, "images/save_as.jpeg",  "E&xit",         "Ctrl+S", "Exit application", qApp.quit)
        
        self.addAction       = ActionWithButton(self.edit_menu, "images/add.jpg",       "Add",           "Ctrl++",       "Exit application", self._addActionHandler)
        self.copyAction      = ActionWithButton(self.edit_menu, "images/copy.png",      "Copy",          "Ctrl+C",       "Exit application", self._copyActionHandler, enabled=False)
        self.pasteAction     = ActionWithButton(self.edit_menu, "images/paste.png",     "Paste",         "Ctrl+V",       "Exit application", self._pasteAfterActionHandler, enabled=False)
        self.pasteBeforeAction = ActionWithButton(self.edit_menu, "images/paste.png",   "Paste Before",  "Ctrl+Shift+V", "Exit application", self._pasteBeforeActionHandler, enabled=False)
        self.removeAction    = ActionWithButton(self.edit_menu, "images/remove.jpg",    "Remove",        "Ctrl+-",       "Exit application", self._removeActionHandler, enabled=False)
        self.checkAction     = ActionWithButton(self.edit_menu, "images/check.jpg",     "Check/Uncheck", "Ctrl+Space",   "Exit application", self._checkActionHandler, enabled=False)
        self.moveUpAction    = ActionWithButton(self.edit_menu, "images/move_up.jpg",   "MoveUp",        "Ctrl+Up",      "Exit application", self._moveUpActionHandler, enabled=False)
        self.moveDownAction  = ActionWithButton(self.edit_menu, "images/move_down.jpg", "MoveDown",      "Ctrl+Down",    "Exit application", self._moveDownActionHandler, enabled=False)
        
        self.startAction     = ActionWithButton(self.run_menu, "images/start.jpg",      "Start",          "Ctrl+F5",      "Exit application",  self._runActionHandler)
        self.stopAction      = ActionWithButton(self.run_menu, "images/stop.jpg",       "Stop",           "Ctrl+F11",     "Exit application", self._stopActionHandler, enabled=False)
        
        self.editAction      = ActionWithButton(self.window_menu, "images/edit.jpg",     "Show edit pane","",       "Exit application", self._showEditPaneAction, checkable=True, checked=True)
        self.closeWinsAction = ActionWithButton(self.window_menu, "images/close_all_windows.jpeg","&Close Open Windows", "Ctrl+X", "Exit application", self._closeAllWindowsAction)
        
        self.aboutAction     = ActionWithButton(self.help_menu, "images/about.jpeg",   "&About",        "F1", "Exit application", self._aboutAction, checkable=True)
        
        #########
        # Panes:
        #########
        sequence_pane = QSplitter()
        sequence_pane.setOrientation(Qt.Vertical)
        sequence_pane.setLayout(QVBoxLayout())
        sequence_pane.layout().addWidget(self.sequence_widget, 2)
        sequence_pane.layout().addWidget(self.configuration_box, 1)
        sequence_pane.resize(500, sequence_pane.height())

        configurations_folder_widget = self.configurations_folder.createWidget()
        configurations_folder_widget.layout().setMargin(0)

        steps_select_pane = QWidget()
        steps_select_pane.setLayout(QVBoxLayout())
        steps_select_pane.layout().setMargin(0)
        steps_select_pane.layout().addWidget(configurations_folder_widget)
        self._log_widget = MultiLogWidget()
        
        logs_pane = QWidget()
        logs_pane.setLayout(QVBoxLayout())
        logs_pane.layout().addWidget(self._log_widget)
        
#         configurations_folder_widget.setObjectName("HighLevelWidget")
#         configurations_folder_widget.setStyleSheet("QWidget#HighLevelWidget { border:1px solid black; }")        

#         self.edit_pane = QWidget()
#         self.edit_pane.setLayout(QVBoxLayout())
#         self.edit_pane.layout().addWidget(steps_select_pane, 1)
#         self.edit_pane.layout().addWidget(QLabel("Properties:"))
        #self.edit_pane.layout().addWidget(self.configuration_pane, 1)

        central_widget = QSplitter()
        central_widget.addWidget(sequence_pane)
        central_widget.addWidget(logs_pane)
        #central_widget.addWidget(self.edit_pane)

        self.setCentralWidget(central_widget)

    #--------------------------------------------------------------------#

    def _log(self, line, process, log_level):
        if (process is None) or (process.log_file_path is None):
            print line
            return
        self._log_widget.log(line, process.log_file_path, log_level)

    #--------------------------------------------------------------------#

    def _openLog(self, process):
        if (process is None) or (process.log_file_path is None):
            return
        process.openLog(verbose=False)
        return self._log_widget.open(process.log_file_path, str(process.title))

    #--------------------------------------------------------------------#

    def _closeLog(self, process):
        if (process is None) or (process.log_file_path is None):
            return        
        process.closeLog()
        self._log_widget.close(process.log_file_path)
                            
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
    
    def _onNewProcess(self, process):
        self.emitOpenLog(process)
        
    #--------------------------------------------------------------------#
    
    def _onProcessDone(self, process):
        if process.instance.returncode in [0, 143, -15]:
            self.emitCloseLog(process)
            return True
        
        self._error_processes.append(process)
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
    
    def _addSequenceCell(self, r, c, text = None, editable = False, checkbox_handler = None, spinbox_handler = None):
        item = QTableWidgetItem()
        flags = item.flags()
        if not editable:
            flags ^= Qt.ItemIsEditable
        item.setFlags(flags)
        #item.setTextAlignment(Qt.AlignCenter)
            
        if checkbox_handler:
            widget = QCheckBox()
            widget.setMaximumWidth(30)
            widget.stateChanged.connect(checkbox_handler)
            self.sequence_widget.setCellWidget(r, c, widget)
        elif spinbox_handler:
            widget = QSpinBox()
            widget.setMaximumWidth(50)
            widget.valueChanged.connect(spinbox_handler)            
            self.sequence_widget.setCellWidget(r, c, widget)
        elif text is not None: 
            item.setText(text)
        self.sequence_widget.setItem(r, c, item)
    
    #--------------------------------------------------------------------#
        
    def _getStepEnabledHandler(self, index):
        def op(val):
            self._setStepEnabled(index, val == Qt.Checked)
            self._setModified()
        return op
    
    #--------------------------------------------------------------------#
        
    def _getStepRepeatHandler(self, index):
        def op(val):
            self._sequence[index].setRepeat(val)
            self._setModified()
        return op
    
    #--------------------------------------------------------------------#
    
    def _onSequenceItemChanged(self, item):
        #print "Changed: (%u, %u)" % (item.row(), item.column())
        index = item.row()
        step = self._sequence[index]
        if item.column() == 3:
            name = str(item.text())
            if name != step.name(): 
                step.setName(name)
        
    #--------------------------------------------------------------------#
    
    def _addStepsToSequence(self, steps, index):
        new_indexes = []
        for step in steps:
            self._sequence.insert(index, step)
            self.sequence_widget.insertRow(index)
            self._addSequenceCell(index, 0, checkbox_handler=self._getStepEnabledHandler(index))
            self._addSequenceCell(index, 1, spinbox_handler=self._getStepRepeatHandler(index))
            self._addSequenceCell(index, 2)
            self._addSequenceCell(index, 3, text = step.name() if step.name() is not None else step.className(), editable=True)
            self._addSequenceCell(index, 4)
            self._updateStepInSequence(index, step)
            new_indexes.append(index)
            index += 1
        return new_indexes
    
    #--------------------------------------------------------------------#

    def _addStepsToSequenceStart(self, steps):
        return self._addStepsToSequence(steps, 0)
    
    #--------------------------------------------------------------------#

    def _addStepsToSequenceEnd(self, steps):
        return self._addStepsToSequence(steps, self.sequence_widget.rowCount())
            
    #--------------------------------------------------------------------#

    def _addStepsToSequenceBefore(self, steps):
        selected_indexes = self._getSelectedIndexes()
        index = 0 if len(selected_indexes) == 0 else min(selected_indexes)
        return self._addStepsToSequence(steps, index)

    #--------------------------------------------------------------------#

    def _addStepsToSequenceAfter(self, steps):
        selected_indexes = self._getSelectedIndexes()
        index = self.sequence_widget.rowCount() if len(selected_indexes) == 0 else max(selected_indexes) + 1
        return self._addStepsToSequence(steps, index)
        
    #--------------------------------------------------------------------#
    
    def _updateStepInSequence(self, index, step):
        self.sequence_widget.cellWidget(index, 0).setChecked(Qt.Checked if step.isEnabled() else Qt.Unchecked)
        self.sequence_widget.cellWidget(index, 1).setValue(step.repeat())
        #self.sequence_widget.item(index, 2).font().setPointSize(50)
        if step.status() == Step.STATUS_IDLE:
            self.sequence_widget.item(index, 2).setText(QString.fromUtf8(""))
            self.sequence_widget.item(index, 2).setForeground(Qt.black)
        elif step.status() == Step.STATUS_RUNNING:
            self.sequence_widget.item(index, 2).setText(QString.fromUtf8("☞"))
            self.sequence_widget.item(index, 2).setForeground(Qt.black)
        elif step.status() == Step.STATUS_PASSED:
            self.sequence_widget.item(index, 2).setText(QString.fromUtf8("✔"))
            self.sequence_widget.item(index, 2).setForeground(Qt.green)
        elif step.status() == Step.STATUS_FAILED:
            self.sequence_widget.item(index, 2).setText(QString.fromUtf8("✘"))
            self.sequence_widget.item(index, 2).setForeground(Qt.red)
        self.sequence_widget.item(index, 4).setText(step.attributesRepr())
        self._setStepEnabled(index, step.isEnabled())
    
    #--------------------------------------------------------------------#
    
    def _setStepEnabled(self, index, val):
        step = self._sequence[index]
        step.setEnabled(val)
#         if self._is_running:
#             self.sequence_widget.cellWidget(index, 0).setEnabled(False)
#             self.sequence_widget.cellWidget(index, 1).setEnabled(False)
#         else:
#             self.sequence_widget.cellWidget(index, 0).setEnabled(True)
#             self.sequence_widget.cellWidget(index, 1).setEnabled(val)
            
#         for col in range(2, self.sequence_widget.columnCount()):
#             item = self.sequence_widget.item(index, col)
#             if val:
#                 item.setFlags(item.flags() | Qt.ItemIsEnabled);
#             else:
#                 item.setFlags(item.flags() & ~Qt.ItemIsEnabled);

    #--------------------------------------------------------------------#
    
    def _moveInSequence(self, delta):
        index = self.sequence_widget.currentRow()
        new_index = index + delta
        if new_index < 0:
            new_index = 0
        if new_index >= self.sequence_widget.rowCount():
            new_index = self.sequence_widget.rowCount() - 1
        if new_index == index:
            return
        
        #print "NEW: %u. OLD: %u." % (new_index, index)
        step1 = self._sequence[index]
        step2 = self._sequence[new_index]
        self._sequence[index] = step2
        self._sequence[new_index] = step1
        self._updateStepInSequence(index, step2)
        self._updateStepInSequence(new_index, step1)
        self.sequence_widget.setCurrentCell(new_index, 0)
        self._setModified()
    
    #--------------------------------------------------------------------#
    
    def _moveUpActionHandler(self):
        self._moveInSequence(-1)
        
    #--------------------------------------------------------------------#
    
    def _moveDownActionHandler(self):
        self._moveInSequence(1)
                    
    #--------------------------------------------------------------------#
    
    def _getSelectedIndexes(self):                    
        return [s.row() for s in self.sequence_widget.selectionModel().selectedRows()]
    
    #--------------------------------------------------------------------#
    
    def _removeSelectedStepsFromSequence(self):
        indexes_to_remove = self._getSelectedIndexes()
        indexes_to_remove.sort(reverse=True)
        for index in indexes_to_remove:
            self._sequence.pop(index)
            while index < len(self._sequence):
                self._updateStepInSequence(index, self._sequence[index])
                index += 1
            self.sequence_widget.removeRow(index)
#         self.sequence_widget.clearSelection()
        self._setModified()

    #--------------------------------------------------------------------#
    
    def _copyStepsToClipboard(self):
        selected_indexes = self._getSelectedIndexes()
        selected_indexes.sort() #reversed=True)
        self._copied_steps = [self._sequence[index].clone() for index in selected_indexes]
        self.pasteAction.setEnabled(True)
        self.pasteBeforeAction.setEnabled(True)
                
    #--------------------------------------------------------------------#
    
    def _pasteStepsToSequence(self, before):
        if len(self._copied_steps) == 0:
            return
        
        if before:
            indexes = self._addStepsToSequenceBefore(self._copied_steps)
        else:
            indexes = self._addStepsToSequenceAfter(self._copied_steps)
        
        if before:
            pass
        else:
            self.sequence_widget.clearSelection()
            print indexes
            for index in indexes:
                self.sequence_widget.selectRow(index)
        self._setModified()        
        
    #--------------------------------------------------------------------#
    
    def _addActionHandler(self):
        prompt = StepEditDialog(self, None)
        res = prompt.exec_()
        if res == QDialog.Accepted:
            indexes = self._addStepsToSequenceAfter([prompt.step()])
            self.sequence_widget.setCurrentCell(indexes[0], 0)
            self._setModified()

    #--------------------------------------------------------------------#
    
    def _copyActionHandler(self):
        self._copyStepsToClipboard()

    #--------------------------------------------------------------------#
    
    def _pasteBeforeActionHandler(self):
        self._pasteStepsToSequence(True)

    #--------------------------------------------------------------------#
    
    def _pasteAfterActionHandler(self):
        self._pasteStepsToSequence(False)
        
    #--------------------------------------------------------------------#
    
    def _checkActionHandler(self):
        selected_indexes = self._getSelectedIndexes()
        all_enabled = all(self._sequence[index].isEnabled() for index in selected_indexes)
        val = Qt.Unchecked if all_enabled else Qt.Checked
        for index in selected_indexes:
            self.sequence_widget.cellWidget(index, 0).setChecked(val)
            self._sequence[index].setEnabled(not all_enabled)
        self._setModified()
                
    #--------------------------------------------------------------------#
    
    def _removeActionHandler(self):
        self._removeSelectedStepsFromSequence()
        
    #--------------------------------------------------------------------#

    def _clear(self):
        while self.sequence_widget.rowCount() > 0:
            self.sequence_widget.removeRow(0)
        self._clearConfigurationPane()
        self._sequence = []

    #--------------------------------------------------------------------#
        
    def _sequenceStepSelected(self, selected, deselected):
        index = self.sequence_widget.currentRow()
        item = self._sequence[index]
        self._setConfigurationPane(item.attributesWidget())
        selected_indexes = self._getSelectedIndexes()
        something_selected = len(selected_indexes) > 0
        self.removeAction.setEnabled(something_selected)
        self.checkAction.setEnabled(something_selected)
        self.copyAction.setEnabled(something_selected)
        self.moveDownAction.setEnabled(something_selected)
        self.moveUpAction.setEnabled(something_selected)

    #--------------------------------------------------------------------#
    
    def _setConfigurationPane(self, widget):
        layout = self.configuration_pane.layout()
        widget_exists = False
        for i in range(layout.count()):
            if widget == layout.itemAt(i).widget():
                widget_exists = True
                break
        
        if not widget_exists:
            widget.addFieldChangedHandler(self._onAttributeChanged)
            layout.insertWidget(0, widget)

        self._attributes_widget.hide()
        self._attributes_widget = widget
        self._attributes_widget.show()
    
    #--------------------------------------------------------------------#
    
    def _clearConfigurationPane(self):
        layout = self.configuration_pane.layout()
        widgets = []
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if w is not None:
                widgets.append(w)
                
        for w in widgets:
            w.hide() 
            w.setParent(None)
        
    #--------------------------------------------------------------------#
    
    def _onAttributeChanged(self, attribute_index, value):
        self._attributes_widget._values[attribute_index] = value 
        step_index = self.sequence_widget.currentRow()
        self._refreshItem(step_index)
        self._setModified()
    
    #--------------------------------------------------------------------#
    
    def _refreshItem(self, index):
        self._updateStepInSequence(index, self._sequence[index])
    
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
            self._setStepStatus(step, index, Step.STATUS_IDLE)
    
    #--------------------------------------------------------------------#
    
    def _setTestLogsDir(self):
        test_name = re.sub("[^0-9a-zA-Z]", "_", os.path.basename(self._doc.filePath()))
        time_prefix = time.strftime("%Y_%m_%d_%H_%M_%S")
        self._test_logs_dir = os.path.join(self._base_logs_dir, time_prefix + "_" + test_name)
        TestEnvironment.Get().setTestLogsDir(self._test_logs_dir)
        
    #--------------------------------------------------------------------#
    
    def _runStep(self, index):
        step = self._sequence[index]
        if not step.isEnabled():
            return True

        self._current_step = step
        self._setStepStatus(step, index, Step.STATUS_RUNNING)
        for count in range(step.repeat()):        
            title("Step %u - %s (%u/%u)" % (index, str(step), count + 1, step.repeat()), style = UniBorder.BORDER_STYLE_DOUBLE)
            res = step.perform(index)
            self._all_passed &= res
            if not res:
                self._setStepStatus(step, index, Step.STATUS_FAILED)                
                if step.stopOnFailure():
                    return False
                break
            
        self._setStepStatus(step, index, Step.STATUS_PASSED)
        return True
                                    
    #--------------------------------------------------------------------#
            
    def _runSequence(self):
        self.emitOpenLog(getMainProcess())
        self._all_passed = True
        self._do_stop = False
        self._reset()
        for index in range(len(self._sequence)):
            if not self._runStep(index):
                break
            if self._do_stop:
                log("Stopped by user.", log_level=LOG_LEVEL_ERROR)
                break
        self._emitRunSequenceDone()
        
    #--------------------------------------------------------------------#
            
    def _runSequenceInNewThread(self):
        self.thread = RunTestSequenceThread(self)
        self.thread.start()
        
    #--------------------------------------------------------------------#
    
    def _runSequenceDone(self):
        log("Done.", log_level = LOG_LEVEL_NOTE)
        getMainProcess().closeLog()
        setMainProcess(None)
        self._is_running = False        
        self._setEditWidgetsEnabled(True)
        for index in range(len(self._sequence)):
            self._refreshItem(index)

    #--------------------------------------------------------------------#
    
    def _setEditWidgetsEnabled(self, val):
        if val:
            self.sequence_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        else:
            self.sequence_widget.clearSelection()
            self.sequence_widget.setSelectionMode(QAbstractItemView.NoSelection)

        #self.sequence_widget.setEnabled(val)
        for action in self.edit_menu.menu.actions():
            action.setEnabled(val)
        self.startAction.setEnabled(val)
        self.stopAction.setEnabled(not val)
        
        # Show/Hide edit pane
        self.editAction.setEnabled(val)
        self.configuration_box.setVisible(val and self.editAction.isChecked())
    
    #--------------------------------------------------------------------#
    
    def _run(self):
        self._saveAction(None)
        self._is_running = True
        self._setEditWidgetsEnabled(False)
        
        self._setTestLogsDir()
        title = "Running: %s" % self._doc.filePath()
        log(title, log_level = LOG_LEVEL_NOTE)
        main_process = BasicProcess(None, title, os.path.join(self._test_logs_dir, "main.log"), None)
        setMainProcess(main_process)
        self._runSequenceInNewThread()
        
    #--------------------------------------------------------------------#
        
    def _stop(self):
        if self._do_stop:
            return
        log("Stopping...", log_level=LOG_LEVEL_ERROR)
        self._do_stop = True
        self._current_step.stop()
    
    #--------------------------------------------------------------------#
        
    def _runActionHandler(self):
        self._run()
    
    #--------------------------------------------------------------------#

    def _stopActionHandler(self):
        self._stop()
    
    #--------------------------------------------------------------------#
    
    def _showEditPaneAction(self, checked):
        self.configuration_box.setVisible(checked)
    
    #--------------------------------------------------------------------#
    
    def _closeAllWindowsAction(self, checked):
        for process in self._error_processes:
            self.emitCloseLog(process)
        self._log_widget.closeAllSubWindows()
    
    #--------------------------------------------------------------------#
    
    def _aboutAction(self):
        pass 
            
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
    
    def _openAction(self, is_checked):
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
            self._addStepsToSequenceEnd([step])
        self._doc.setModified(False)
            
    #--------------------------------------------------------------------#
    
    def run(self):
        self._run()
        self.thread.wait()
    
    #--------------------------------------------------------------------#
    
#     def keyPressEvent(self, event):
#         if (event.key() == Qt.Key_C) and (event.modifiers() & Qt.ControlModifier):
#             self._copyStepsToClipboard()
#         elif (event.key() == Qt.Key_V) and (event.modifiers() & Qt.ControlModifier):
#             before = bool(event.modifiers() & Qt.ShiftModifier)
#             self._pasteStepsToSequence(before)
    
    #--------------------------------------------------------------------#
    
    # Override:
    def closeEvent(self, evnt):
        if not self._doc.close():
            evnt.ignore()
            return
        super(MLTester, self).closeEvent(evnt)
                
###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################
        
if __name__ == '__main__':
    
    arg_parser = argparse.ArgumentParser(description = "ML tester")
    arg_parser.add_argument("xml", nargs="?", help="A test file to load.")
    arg_parser.add_argument("-a", "--autorun", action="store_true", help="Automatic regression run (no GUI).")
    arg_parser.add_argument("-L", "--log_level", type=int, default="3", help="Log level.")    
    
    args = arg_parser.parse_args()
#     QApplication.setStyle(QStyleFactory.create("motif"))
#     QApplication.setStyle(QStyleFactory.create("Windows"))
#     QApplication.setStyle(QStyleFactory.create("cde"))
#     QApplication.setStyle(QStyleFactory.create("Plastique"))
    QApplication.setStyle(QStyleFactory.create("Cleanlooks"))
    
#     QApplication.setStyle(QStyleFactory.create("windowsvista"))
    app = QApplication([])
    prompt = MLTester()
    if args.xml is not None:
        prompt.loadFromXml(args.xml)
    
    if args.autorun:
        setLogLevel(args.log_level, LOG_LEVEL_ALL)        
        prompt.run()
    else:
        setLogLevel(LOG_LEVEL_INFO, LOG_LEVEL_ALL)
        prompt.setTestEnvironment()
        prompt.loadFromXml("samples/performance_regression.xml")
#         prompt.setGeometry(200, 30, 1900, 800)
        prompt.showMaximized()
        prompt.show()
        app.exec_()
