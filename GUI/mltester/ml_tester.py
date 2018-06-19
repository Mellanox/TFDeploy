#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import os
import pkg_resources
import re
import sys
import threading
import time
import traceback
from xml.dom import minidom
from xml.etree import cElementTree as etree
from PyQt4.Qt import QWidget, QIcon, QMainWindow, pyqtSignal, QTableWidget, \
    QHeaderView, QAbstractItemView, QVBoxLayout, QScrollArea, QSplitter, \
    QTableWidgetItem, QCheckBox, QSpinBox, QMessageBox, qApp, QString, Qt, \
    QDialog, QApplication, QStyleFactory, QTabWidget, QStackedWidget, QFont

from commonpylib.gui import DocumentControl, MultiLogWidget, DefaultAttributesWidget
from commonpylib.log import LOG_LEVEL_INFO, LogManager, openLog, LogLevelNames, error, info, title
from commonpylib.util import BasicProcess, WorkerThread, NestedException, PathAttribute, EnumAttribute, configurations, AttributesList
from actions import TestEnvironment, Step
from dialogs import StepEditDialog
from dialogs.common_widgets import MenuWithToolbar, ActionWithButton,\
    VariablesAttribute, TestDataFolder, TestDataAttribute

#############################################################################
# General        
#############################################################################

LAST_OPENED_FILE = "LAST_OPENED_FILE"
GEOMETRY = "GEOMETRY"
GEOMETRY_MAX = "max"

home_dir = os.path.expanduser("~")
default_logs_dir = os.path.join(home_dir, "mltester_logs")
conf = configurations.Conf(os.path.join(os.path.expanduser("~"), ".mltester"))

#--------------------------------------------------------------------#

def _res(resource_path):
    pkg_name = os.path.basename(os.path.dirname(__file__))
    return pkg_resources.resource_filename(pkg_name, resource_path)

#--------------------------------------------------------------------#

TestAttributeDescriptors = [PathAttribute("base_log_dir", "Logs Folder", default_logs_dir),
                            # TODO: MOVE TO PREFERENCES:
                            EnumAttribute("log_level", "Log Level",  LogLevelNames[LOG_LEVEL_INFO], possible_values = LogLevelNames), 
                            EnumAttribute("file_log_level", "File Log Level", LogLevelNames[LOG_LEVEL_INFO], possible_values = LogLevelNames)]

#############################################################################

class MLTester(object):
    
    def __init__(self):
        self.sequence = []
        self.settings = AttributesList(TestAttributeDescriptors)
        self._xml_path = None
        self._test_logs_dir = None
        self._step_logs_dir = None
        self._current_step = None
        self._is_running = False
        self._do_stop = False
        self._exception = None
        
        # Event handlers:
        self.run_done_handler = None
        self.step_status_changed_handler = None
    
    #--------------------------------------------------------------------#
    
    def _notifyStepStatusChanged(self, index):
        if self.step_status_changed_handler:
            self.step_status_changed_handler(index)
    
    #--------------------------------------------------------------------#
    
    def _notifyRunDone(self):
        if self.run_done_handler:
            self.run_done_handler()
    
    #--------------------------------------------------------------------#
    
    def _setStepStatus(self, step, index, status):
        step.setStatus(status)
        self._notifyStepStatusChanged(index)
    
    #--------------------------------------------------------------------#
    
    def _reset(self):
        for index in range(len(self.sequence)):
            step = self.sequence[index]
            self._setStepStatus(step, index, Step.STATUS_IDLE)
    
    #--------------------------------------------------------------------#
    
    def _runStep(self, index):
        step = self.sequence[index]
        if not step.isEnabled():
            return True

        self._current_step = step
        self._setStepStatus(step, index, Step.STATUS_RUNNING)
        for count in range(step.repeat()):
            title("Step %u - %s (%u/%u)" % (index, str(step), count + 1, step.repeat()), style = 2)
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
        try:
            self._reset()
            self._all_passed = True
            self._do_stop = False
            for index in range(len(self.sequence)):
                if not self._runStep(index):
                    break
                if self._do_stop:
                    error("Stopped by user.")
                    break
            info("Done.")
            LogManager.Get().main_process.closeLog()
            LogManager.Get().main_process = None
        except Exception:
            message = "Exception occurred on _runSequence()"
            print message
            self._exception = NestedException(message)
        self._is_running = False
        self._notifyRunDone()
    
    #--------------------------------------------------------------------#
    
    def _isRunning(self):
        return self._is_running
    
    #--------------------------------------------------------------------#
    
    def _setLogLevels(self, log_level, file_log_level):
        LogManager.Get().log_level = log_level
        LogManager.Get().file_log_level = file_log_level
    
    #--------------------------------------------------------------------#
    
    def _setTestLogsDir(self, base_log_dir, xml_path):
        test_name = re.sub("[^0-9a-zA-Z]", "_", os.path.basename(xml_path))
        time_prefix = time.strftime("%Y_%m_%d_%H_%M_%S")
        self._test_logs_dir = os.path.join(base_log_dir, time_prefix + "_" + test_name)
        TestEnvironment.Get().setTestLogsDir(self._test_logs_dir)
    
    #--------------------------------------------------------------------#
    
    def _run(self):
        self._is_running = True
        self._setLogLevels(self.settings.log_level, self.settings.file_log_level)
        self._setTestLogsDir(self.settings.base_log_dir, self._xml_path)
        message = "Running: %s" % self._xml_path
        main_process = BasicProcess(None, message, os.path.join(self._test_logs_dir, "main.log"), None)
        LogManager.Get().main_process = main_process
        openLog(LogManager.Get().main_process)
        title(message, style = 1)
        self.thread = WorkerThread(target=self._runSequence)
        self.thread.start()
    
    #--------------------------------------------------------------------#
    
    def _saveToContent(self):
        xml = etree.Element("root")
        settings_xml = etree.SubElement(xml, "Settings")
        self.settings.writeToXml(settings_xml)
        sequence_xml = etree.SubElement(xml, "Sequence")
        for step in self.sequence:
            step.writeToXml(sequence_xml)
        content = minidom.parseString(etree.tostring(xml)).toprettyxml()
        return content
    
    #--------------------------------------------------------------------#
    
    def _loadFromContent(self, content):
        root_node = etree.fromstring(content)
        for xml_node in root_node.getchildren():
            if xml_node.tag == "Sequence":
                self.sequence = []
                for step_node in xml_node.getchildren():
                    step = Step.loadFromXml(step_node)
                    self.sequence.append(step)
            elif xml_node.tag == "Settings":
                self.settings.loadFromXml(xml_node)
    
    #--------------------------------------------------------------------#
    
    def saveToXml(self, xml_path):
        content = self._saveToContent()
        try:
            with open(xml_path, "w") as xml_file:
                xml_file.write(content)
        except IOError, e:
            sys.stderr.write("Failed to write to xml file: %s\n" % e)
    
    #--------------------------------------------------------------------#
    
    def loadFromXml(self, xml_path):
        try:
            with open(xml_path, "r") as xml_file:
                content = xml_file.read()
        except IOError, e:
            sys.stderr.write("Failed to read from xml file: %s\n" % e)
            return
        self._loadFromContent(content)
        self._xml_path = xml_path
    
    #--------------------------------------------------------------------#
    
    def run(self):
        if self._xml_path is None:
            return
        self._run()
    
    #--------------------------------------------------------------------#
    
    def isRunning(self):
        return self._isRunning()
    
    #--------------------------------------------------------------------#
    
    def wait(self):
        if self._isRunning():
            self.thread.join()
    
    #--------------------------------------------------------------------#
    
    def getException(self):
        return self._exception
    
    #--------------------------------------------------------------------#
    
    def stop(self):
        if self._do_stop:
            return
        error("Stopping...")
        self._do_stop = True
        self._current_step.stop()

#############################################################################

class MLTesterDialog(QMainWindow):
    
    open_log_signal = pyqtSignal(object)
    close_log_signal = pyqtSignal(object)
    refresh_item_signal = pyqtSignal(int)
    run_sequence_done_signal = pyqtSignal()
    
    #--------------------------------------------------------------------#
    
    def __init__(self, test_xml_path = None, parent = None):
        super(MLTesterDialog, self).__init__(parent)
        self._tester = MLTester()
        self._tester.step_status_changed_handler = self._emitRefreshItem
        self._tester.run_done_handler = self._emitRunDone
        
        self._doc = DocumentControl(self, "ML tester", "Xml file (*.xml);;Any File (*.*);;", ".")
        self._step_attribute_widgets = {}
        self._copied_steps = []
        self._cell_being_edited = None
        self._error_lock = threading.Lock()
        self._error_message = None
        self._error_processes = []
        self._initGui()
        
        if test_xml_path is not None:
            self._loadFromXml(test_xml_path)
    
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
    
    def _initGui(self):
        
        self.setStyleSheet('''
            QPushButton { background-color: white } 
            QPushButton:hover { background-color: #cccccc }
            ''')
        self.setWindowIcon(QIcon("/usr/share/icons/Humanity/categories/16/preferences-desktop.svg"))
        self.open_log_signal.connect(self._openLogWindow)
        self.close_log_signal.connect(self._closeLogWindow)
        self.refresh_item_signal.connect(self._refreshItem)
        self.run_sequence_done_signal.connect(self._runDone)
        
#         self.sequence_widget = QListWidget()
        self.sequence_widget = QTableWidget()
        self.sequence_widget.setColumnCount(5)
        self.sequence_widget.verticalHeader().setVisible(False)
        self.sequence_widget.setHorizontalHeaderLabels(["", "#", "", "Name", "Attributes"])
        self.sequence_widget.horizontalHeader().setResizeMode(0, QHeaderView.ResizeToContents)
        self.sequence_widget.horizontalHeader().setResizeMode(1, QHeaderView.ResizeToContents)
        self.sequence_widget.horizontalHeader().setResizeMode(2, QHeaderView.ResizeToContents)
        self.sequence_widget.horizontalHeader().setResizeMode(3, QHeaderView.ResizeToContents)
        self.sequence_widget.horizontalHeader().setResizeMode(4, QHeaderView.Stretch)
        self.sequence_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sequence_widget.selectionModel().selectionChanged.connect(self._sequenceStepSelected)
        self.sequence_widget.itemChanged.connect(self._onSequenceItemChanged)
        self.sequence_widget.itemDoubleClicked.connect(self._onItemDoubleClicked)
        self.sequence_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.configuration_pane = QStackedWidget()
        self.configuration_pane.addWidget(QWidget())

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
#         self._createAttribute(self.backup_folder,   "Do Backup", {"False": 0, "True": 1},   "True",   False,    create_combo_box) 
#         self._createAttribute(self.monitors_folder, "Reg",       {"False": 0, "True": 1},   "True",   True,     create_combo_box)
#         self._createAttribute(self.monitors_folder, "Monitor",   None,                      "True",   True,     create_combo_box)        
        
        attribute = VariablesAttribute("Variables")
        self.variables_folder.addAttribute(attribute)
        
        #########
        # Menus:
        #########
                          
        self.file_menu       = MenuWithToolbar(self, "&File")
        self.edit_menu       = MenuWithToolbar(self, "&Edit")
        self.run_menu        = MenuWithToolbar(self, "&Run")
        self.window_menu     = MenuWithToolbar(self, "&Window")
        self.help_menu       = MenuWithToolbar(self, "&Help")
                
        self.newAction       = ActionWithButton(self.file_menu,   _res("images/new.jpeg"),             "&New",             "Ctrl+N",       self._newActionHandler)
        self.openAction      = ActionWithButton(self.file_menu,   _res("images/open.jpeg"),            "&Open...",         "Ctrl+O",       self._openActionHandler)
        self.saveAction      = ActionWithButton(self.file_menu,   _res("images/save.jpeg"),            "&Save",            "Ctrl+S",       self._saveActionHandler)
        self.saveAsAction    = ActionWithButton(self.file_menu,   _res("images/save_as.jpeg"),         "Save &As...",      "",             self._saveAsActionHandler)
        self.file_menu.menu.addSeparator()
        self.quitAction      = ActionWithButton(self.file_menu,   _res("images/save_as.jpeg"),         "E&xit",            "Alt+F4",       self._quitActionHandler)
                                                                                                                                    
        self.addAction       = ActionWithButton(self.edit_menu,   _res("images/add.jpg"),              "Add...",           "Ctrl++",       self._addActionHandler)
        self.cutAction       = ActionWithButton(self.edit_menu,   _res("images/cut.png"),              "Cut",              "Ctrl+X",       self._cutActionHandler, enabled=False)
        self.copyAction      = ActionWithButton(self.edit_menu,   _res("images/copy.png"),             "Copy",             "Ctrl+C",       self._copyActionHandler, enabled=False)
        self.pasteAction     = ActionWithButton(self.edit_menu,   _res("images/paste.png"),            "Paste",            "Ctrl+V",       self._pasteAfterActionHandler, enabled=False)
        self.pasteBeforeAction = ActionWithButton(self.edit_menu, _res("images/paste.png"),            "Paste Before",     "Ctrl+Shift+V", self._pasteBeforeActionHandler, enabled=False)
        self.removeAction    = ActionWithButton(self.edit_menu,   _res("images/remove.jpg"),           "Remove",           "Del",          self._removeActionHandler, enabled=False)
        self.checkAction     = ActionWithButton(self.edit_menu,   _res("images/check.jpg"),            "Check/Uncheck",    "Ctrl+Space",   self._checkActionHandler, enabled=False)
        self.moveUpAction    = ActionWithButton(self.edit_menu,   _res("images/move_up.jpg"),          "MoveUp",           "Ctrl+Up",      self._moveUpActionHandler, enabled=False)
        self.moveDownAction  = ActionWithButton(self.edit_menu,   _res("images/move_down.jpg"),        "MoveDown",         "Ctrl+Down",    self._moveDownActionHandler, enabled=False)
        
        self.startAction     = ActionWithButton(self.run_menu,    _res("images/start.jpg"),            "Start",            "Ctrl+F5",      self._runActionHandler)
        self.stopAction      = ActionWithButton(self.run_menu,    _res("images/stop.jpg"),             "Stop",             "Ctrl+F11",     self._stopActionHandler, enabled=False)
        
        self.closeWinsAction = ActionWithButton(self.window_menu, _res("images/close_windows.jpeg"),   "&Close Windows",    "",            self._closeAllWindowsActionHandler)
        self.closeWinsAction = ActionWithButton(self.window_menu, _res("images/cascade_windows.jpeg"), "C&ascade Windows",  "",            self._cascadeWindowsActionHandler)
        self.closeWinsAction = ActionWithButton(self.window_menu, _res("images/tile_windows.jpeg"),    "&Tile Windows",     "",            self._tileWindowsActionHandler)
        self.editAction      = ActionWithButton(self.window_menu, _res("images/edit.jpg"),             "Show &Edit Pane",  "Ctrl+E",       self._showEditPaneActionHandler, checkable=True, checked=True)
        self.showNaviAction  = ActionWithButton(self.window_menu, _res("images/show_navigator.jpeg"),  "Show &Navigator",  "Ctrl+R",       self._showNavigatorActionHandler, checkable=True, checked=True)
        self.showGraphsAction= ActionWithButton(self.window_menu, _res("images/graphs.jpeg"),          "Show Graphs",      "Ctrl+G",       self._showGraphsActionHandler, enabled=False)
        #self.window_menu.menu.addSeparator()
        #self.moveDownAction  = ActionWithButton(self.window_menu,_res("images/preferences.png"),      "Preferences",      "",             self._preferencesActionHandler)        
        
        self.aboutAction     = ActionWithButton(self.help_menu,   _res("images/about.jpeg"),            "&About",           "F1",           self._aboutActionHandler)
        
        #########
        # Panes:
        #########
        sequence_pane = QSplitter()
        sequence_pane.setOrientation(Qt.Vertical)
        sequence_pane.setLayout(QVBoxLayout())
        sequence_pane.layout().addWidget(self.sequence_widget, 2)
        sequence_pane.layout().addWidget(self.configuration_box, 1)
        
        self.settings_pane = DefaultAttributesWidget(TestAttributeDescriptors)
        self.settings_pane.addFieldChangedHandler(self._onSettingsAttributeChanged)
        
        self._log_widget = MultiLogWidget()
        logs_pane = QWidget()
        logs_pane.setLayout(QVBoxLayout())
        logs_pane.layout().addWidget(self._log_widget)
        
#         configurations_folder_widget.setObjectName("HighLevelWidget")
#         configurations_folder_widget.setStyleSheet("QWidget#HighLevelWidget { border:1px solid black; }")        
        
        edit_pane = QTabWidget()
        edit_pane.addTab(sequence_pane, "Test Sequence")
        edit_pane.addTab(self.settings_pane, "Test Settings")
        edit_pane.resize(500, edit_pane.height())
        
        central_widget = QSplitter()
        central_widget.addWidget(edit_pane)
        central_widget.addWidget(logs_pane)
        #central_widget.addWidget(self.edit_pane)
        
        self.setCentralWidget(central_widget)
        
        ###############
        # Status Bar: #
        ###############
        #self.statusBar().addWidget(self.status_text, 1)
    
    #--------------------------------------------------------------------#
    
    def _logToWidget(self, line, process, log_level):
        if (process is None) or (process.log_file_path is None):
            print line
            return
        self._log_widget.log(line, process.log_file_path, log_level)
    
    #--------------------------------------------------------------------#
    
    def _openLogWindow(self, process):
        if (process is None) or (process.log_file_path is None):
            return
        process.openLog()
        return self._log_widget.open(process.log_file_path, str(process.title))
    
    #--------------------------------------------------------------------#
    
    def _closeLogWindow(self, process):
        if (process is None) or (process.log_file_path is None):
            return
        process.closeLog()
        self._log_widget.close(process.log_file_path)
    
    #--------------------------------------------------------------------#
    
    def _setModified(self):
        self._doc.setModified(True)
    
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
            self._tester.sequence[index].setRepeat(val)
            self._setModified()
        return op
    
    #--------------------------------------------------------------------#
    
    def _onItemDoubleClicked(self, item):
        row = item.row()
        col = item.column()
        #print "ITEM DOUBLE CLICKED: (%u, %u)" % (row, col)
        if col != 3:
            return
        self._cell_being_edited = (row, col)
    
    #--------------------------------------------------------------------#
    
    def _onSequenceItemChanged(self, item):
        if self._cell_being_edited is None:
            return
        row = item.row()
        col = item.column()
        edited_row, edited_col = self._cell_being_edited
        if (row != edited_row) or (col != edited_col):
            return
        
        #print "Changed: (%u, %u)" % (row, col)
        index = row
        step = self._tester.sequence[index]
        if item.column() == 3:
            name = str(item.text())
            if name != step.name(): 
                step.setName(name)
        self._cell_being_edited = None
        self._setModified()
    
    #--------------------------------------------------------------------#
    
    def _addStepToWidget(self, index, step):
        self.sequence_widget.insertRow(index)
        self._addSequenceCell(index, 0, checkbox_handler=self._getStepEnabledHandler(index))
        self._addSequenceCell(index, 1, spinbox_handler=self._getStepRepeatHandler(index))
        self._addSequenceCell(index, 2)
        self._addSequenceCell(index, 3, text = step.name(), editable=True)
        self._addSequenceCell(index, 4)
        self._updateStepInWidget(index, step)
    
    #--------------------------------------------------------------------#
    
    def _addStepsToSequence(self, steps, index):
        new_indexes = []
        for step in steps:
            self._tester.sequence.insert(index, step)
            self._addStepToWidget(index, step)
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
    
    def _updateStepInWidget(self, index, step):
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
        self.sequence_widget.item(index, 3).setText(step.name())
        self.sequence_widget.item(index, 4).setText(step.attributesRepr())
        self._setStepEnabled(index, step.isEnabled())
    
    #--------------------------------------------------------------------#
    
    def _setStepEnabled(self, index, val):
        step = self._tester.sequence[index]
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
        step1 = self._tester.sequence[index]
        step2 = self._tester.sequence[new_index]
        self._tester.sequence[index] = step2
        self._tester.sequence[new_index] = step1
        self._updateStepInWidget(index, step2)
        self._updateStepInWidget(new_index, step1)
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
            self._tester.sequence.pop(index)
            while index < len(self._tester.sequence):
                self._updateStepInWidget(index, self._tester.sequence[index])
                index += 1
            self.sequence_widget.removeRow(index)
        self.sequence_widget.clearSelection()
        self._setModified()
    
    #--------------------------------------------------------------------#
    
    def _copyStepsToClipboard(self):
        selected_indexes = self._getSelectedIndexes()
        selected_indexes.sort() #reversed=True)
        self._copied_steps = [self._tester.sequence[index] for index in selected_indexes]
        self.pasteAction.setEnabled(True)
        self.pasteBeforeAction.setEnabled(True)
    
    #--------------------------------------------------------------------#
    
    def _pasteStepsToSequence(self, before):
        if len(self._copied_steps) == 0:
            return
        
        clones = [step.clone() for step in self._copied_steps]
        if before:
            indexes = self._addStepsToSequenceBefore(clones)
        else:
            indexes = self._addStepsToSequenceAfter(clones)
        
        if before:
            pass
        else:
            self.sequence_widget.clearSelection()
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
    
    def _cutActionHandler(self):
        self._copyStepsToClipboard()
        self._removeSelectedStepsFromSequence()
        
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
        all_enabled = all(self._tester.sequence[index].isEnabled() for index in selected_indexes)
        val = Qt.Unchecked if all_enabled else Qt.Checked
        for index in selected_indexes:
            self.sequence_widget.cellWidget(index, 0).setChecked(val)
            self._tester.sequence[index].setEnabled(not all_enabled)
        self._setModified()
                
    #--------------------------------------------------------------------#
    
    def _removeActionHandler(self):
        self._removeSelectedStepsFromSequence()
        
    #--------------------------------------------------------------------#

    def _clear(self):
        while self.sequence_widget.rowCount() > 0:
            self.sequence_widget.removeRow(0)
        self._clearConfigurationPane()
    
    #--------------------------------------------------------------------#
    
    def _syncGui(self):
        # TODO: Completely sync the GUI with the tester
        self._clear()
        self.settings_pane.load(self._tester.settings)
        for index in range(len(self._tester.sequence)):
            step = self._tester.sequence[index]
            self._addStepToWidget(index, step)
        self._doc.setModified(False) # Patch: the above actions marked as modified
    
    #--------------------------------------------------------------------#
    
    def _sequenceStepSelected(self, selected, deselected):
        index = self.sequence_widget.currentRow()
        if index == -1:
            self._clearConfigurationPane()
            return

        step = self._tester.sequence[index]
        self._setConfigurationPane(step)
        selected_indexes = self._getSelectedIndexes()
        something_selected = len(selected_indexes) > 0
        enable_edit = not self._tester.isRunning() and something_selected
        self.removeAction.setEnabled(enable_edit)
        self.checkAction.setEnabled(enable_edit)
        self.copyAction.setEnabled(enable_edit)
        self.cutAction.setEnabled(enable_edit)
        self.moveDownAction.setEnabled(enable_edit)
        self.moveUpAction.setEnabled(enable_edit)
        self.showGraphsAction.setEnabled(something_selected)
        self._cell_being_edited = None

    #--------------------------------------------------------------------#
    
    def _setConfigurationPane(self, step):
        step_class = type(step)
        widget, index = self._step_attribute_widgets.get(step_class, (None, None))
        if index is None:
            widget = step_class.GET_WIDGET()
            widget.addFieldChangedHandler(self._onStepAttributeChanged)
            self.configuration_pane.addWidget(widget)
            index = self.configuration_pane.count() - 1
            self._step_attribute_widgets[step_class] = (widget, index)
        widget.load(step.attributes())
        self.configuration_pane.setCurrentIndex(index)
    
    #--------------------------------------------------------------------#
    
    def _clearConfigurationPane(self):
        self.configuration_pane.setCurrentIndex(0)
    
    #--------------------------------------------------------------------#
    
    def _onSettingsAttributeChanged(self, attribute_index, value):
        self._setModified()
        
    #--------------------------------------------------------------------#
    
    def _onStepAttributeChanged(self, attribute_index, value):
        step_index = self.sequence_widget.currentRow()
        step = self._tester.sequence[step_index]
        step.attributes()[attribute_index].val = value
        self._refreshItem(step_index)
        self._setModified()
    
    #--------------------------------------------------------------------#
    
    def _refreshItem(self, index):
        self._updateStepInWidget(index, self._tester.sequence[index])
    
    #--------------------------------------------------------------------#
    
    def _emitRefreshItem(self, index):
        self.refresh_item_signal.emit(index)
    
    #--------------------------------------------------------------------#
    
    def _emitRunDone(self):
        self.run_sequence_done_signal.emit()
    
    #--------------------------------------------------------------------#
    
    def _setEditWidgetsEnabled(self, val):
        if val:
            pass
#             self.sequence_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        else:
            self.sequence_widget.clearSelection()
#             self.sequence_widget.setSelectionMode(QAbstractItemView.NoSelection)
        #self.sequence_widget.setEnabled(val)
        selected_indexes = self._getSelectedIndexes()
        for action in self.edit_menu.menu.actions():
            action.setEnabled(val)
        self.cutAction.setEnabled(val and (len(selected_indexes) > 0))
        self.copyAction.setEnabled(val and (len(selected_indexes) > 0))
        self.pasteAction.setEnabled(val and (len(self._copied_steps) > 0))
        self.pasteBeforeAction.setEnabled(val and (len(self._copied_steps) > 0))
        self.startAction.setEnabled(val)
        self.stopAction.setEnabled(not val)
        
        # Show/Hide edit pane
        self.editAction.setEnabled(val)
        self.configuration_box.setVisible(val and self.editAction.isChecked())
    
    #--------------------------------------------------------------------#
    
    def _runDone(self):
        ex = self._tester.getException()
        if ex:
            raise ex
        
        self._setEditWidgetsEnabled(True)
        for index in range(len(self._tester.sequence)):
            self._refreshItem(index)
    
    #--------------------------------------------------------------------#
    
    def _run(self):
        self._saveToXml()
        self._setEditWidgetsEnabled(False)
        self._tester.run() 
    
    #--------------------------------------------------------------------#
        
    def _stop(self):
        self._tester.stop()
    
    ###########################################################################
    #                             Action handlers                             #
    ###########################################################################
    
    def _runActionHandler(self):
        self._run()
    
    #--------------------------------------------------------------------#
    
    def _stopActionHandler(self):
        self._stop()
    
    #--------------------------------------------------------------------#
    
    def _showEditPaneActionHandler(self, checked):
        self.configuration_box.setVisible(checked)
    
    #--------------------------------------------------------------------#
    
    def _closeAllWindowsActionHandler(self, checked):
        for process in self._error_processes:
            self.close_log_signal.emit(process)
        self._log_widget.hideAllSubWindows()
    
    #--------------------------------------------------------------------#
    
    def _cascadeWindowsActionHandler(self, checked):
        self._log_widget.cascadeSubWindows()
    
    #--------------------------------------------------------------------#
    
    def _tileWindowsActionHandler(self, checked):
        self._log_widget.tileSubWindows()
    
    #--------------------------------------------------------------------#
    
    def _showNavigatorActionHandler(self, checked):
        self._log_widget.navigator().setVisible(checked)
    
    #--------------------------------------------------------------------#
    
    def _showGraphsActionHandler(self, checked):
        from mltester import ml_graph_viewer
        selected_indexes = self._getSelectedIndexes()
        dirs = []
        for index in selected_indexes:
            step = self._tester.sequence[index]
            logs_dir = step.logsDir()
            if logs_dir is not None:
                dirs.append(logs_dir)
                
        if len(dirs) > 0:
            dialog = ml_graph_viewer(dirs, parent = self)
            dialog.show()
    
    #--------------------------------------------------------------------#
    
    def _preferencesActionHandler(self):
        pass
        #prompt = PreferencesDialog(self)
        #res = prompt.exec_()
        #if res == QDialog.Accepted:
        #    self._setModified()
    
    #--------------------------------------------------------------------#
    
    def _aboutActionHandler(self):
        msg = """ MLTester 
        """
        
        QMessageBox.about(self, "ML Tester", msg.strip())
    
    #--------------------------------------------------------------------#
    
    def _newActionHandler(self):
        self._doc.new()
        self._clear()
    
    #--------------------------------------------------------------------#
    
    def _openActionHandler(self, is_checked):
        self._loadFromXml()
    
    #--------------------------------------------------------------------#
    
    def _saveActionHandler(self, is_checked):
        self._saveToXml()
    
    #--------------------------------------------------------------------#
    
    def _saveAsActionHandler(self, is_checked):
        content = self._getXmlContent()
        self._doc.saveAs(content)
    
    #--------------------------------------------------------------------#
    
    def _quitActionHandler(self, is_checked):
        qApp.quit
    
    #--------------------------------------------------------------------#
    
    def _loadFromXml(self, file_path):
        file_path = self._doc.load(file_path)
        if file_path is None:
            return
        
        conf.set(LAST_OPENED_FILE, self._doc.filePath())
        self._tester.loadFromXml(file_path)
        self._syncGui()
    
    #--------------------------------------------------------------------#
    
    def _saveToXml(self):
        if not self._doc.save():
            return
        
        conf.set(LAST_OPENED_FILE, self._doc.filePath())
        self._tester.saveToXml(self._doc.filePath())
    
    ###########################################################################
    #                             QMainWindow Hooks                           #
    ###########################################################################
    
#     def keyPressEvent(self, event):
#         if (event.key() == Qt.Key_C) and (event.modifiers() & Qt.ControlModifier):
#             self._copyStepsToClipboard()
#         elif (event.key() == Qt.Key_V) and (event.modifiers() & Qt.ControlModifier):
#             before = bool(event.modifiers() & Qt.ShiftModifier)
#             self._pasteStepsToSequence(before)
    
    #--------------------------------------------------------------------#
    
    def closeEvent(self, evnt):
        geometry = GEOMETRY_MAX if self.isMaximized() else "%u,%u,%u,%u" % (self.x(), self.y(), self.width(), self.height())
        conf.set(GEOMETRY, geometry)
        if not self._doc.close():
            evnt.ignore()
            return
        super(MLTesterDialog, self).closeEvent(evnt)
    
    ###########################################################################
    #                         Log/Environment Handlers                        #
    ###########################################################################
    
    def openLogOp(self, process):
        self.open_log_signal.emit(process)
    
    #--------------------------------------------------------------------#
    
    def closeLogOp(self, process):
        self.close_log_signal.emit(process)
    
    # -------------------------------------------------------------------- #
    
    def logOp(self, line, process, log_level): 
        # Emit is not required, since the log widget does async plotting
        self._logToWidget(line, process, log_level) 
    
    # -------------------------------------------------------------------- #
    
    def makeTitleOp(self, msg, style, process):
        if style <= 0:
            msg = "<h1>%s</h1>" % msg
        elif style <= 10:
            msg = "<h%u>%s</h%u>" % (style, msg, style)
        return msg
        
    # -------------------------------------------------------------------- #
    
    def onNewProcess(self, process):
        self.open_log_signal.emit(process)
        
    #--------------------------------------------------------------------#
    
    def onProcessDone(self, process):
        if process.exception is not None:
            raise process.exception
            
        if process.instance.returncode in [0, 143, -15]:
            self.close_log_signal.emit(process)
            return True
        
        self._error_processes.append(process)
        return False

    #--------------------------------------------------------------------#
    
    def exceptionHook(self, etype, value, tb):
        title = "Internal Error"
        trace = "".join(traceback.format_exception(etype, value, tb))
        
        #####################
        # Only prompt once: #
        #####################
        with self._error_lock:
            if self._error_message is None:
                self._error_message = value

        sys.stderr.write(trace)
        if self.isVisible() and (self._error_message == value):
            QMessageBox.critical(self, title, "An exception had occurred. See stderr for details.")
            #msg = QLabel(trace, parent=self)
            #msg.setStyleSheet("QLabel{max-width: 500px; height: 500px; min-height: 500px; max-height: 500px;}")
            #msg.show()
        #sys.__excepthook__(etype, value, tb)

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

def runCLI(test_xml_path):
    if test_xml_path is None:
        print "An XML must be specified when using autorun."
        return
    
    tester = MLTester()
    tester.loadFromXml(test_xml_path)
    tester.run()
    tester.wait()
    ex = tester.getException()
    if ex:
        raise ex

#--------------------------------------------------------------------#

def runGUI(test_xml_path):
    # QApplication.setStyle(QStyleFactory.create("motif"))
    # QApplication.setStyle(QStyleFactory.create("Windows"))
    # QApplication.setStyle(QStyleFactory.create("cde"))
    # QApplication.setStyle(QStyleFactory.create("Plastique"))
    QApplication.setStyle(QStyleFactory.create("Cleanlooks"))
    # QApplication.setStyle(QStyleFactory.create("windowsvista"))
    QApplication.setFont(QFont("Sans", 9, QFont.Normal));
    
    app = QApplication([])
    prompt = MLTesterDialog(test_xml_path)
    TestEnvironment.Get().on_new_process = prompt.onNewProcess
    TestEnvironment.Get().on_process_done = prompt.onProcessDone
    LogManager.Get().log_op = prompt.logOp
    LogManager.Get().error_op = prompt.logOp
    LogManager.Get().make_title_op = prompt.makeTitleOp
    LogManager.Get().open_log_op = prompt.openLogOp
    LogManager.Get().close_log_op = prompt.closeLogOp
    sys.excepthook = prompt.exceptionHook 
    
    geometry = conf.get(GEOMETRY)
    if geometry == GEOMETRY_MAX:
        prompt.showMaximized()
    else:
        try:
            pair = geometry.split(",")
            prompt.setGeometry(int(pair[0]) + 2, int(pair[1]) + 23, int(pair[2]), int(pair[3]))
        except:
            pass
        prompt.show()
    
    app.exec_()

#--------------------------------------------------------------------#

def main():
    arg_parser = argparse.ArgumentParser(description = "ML tester")
    arg_parser.add_argument("xml", nargs="?", help="A test file to load.")
    arg_parser.add_argument("-a", "--autorun", action="store_true", help="Automatic regression run (no GUI).")
    
    args = arg_parser.parse_args()
    
    conf.read()
    test_xml_path = args.xml if args.xml else conf.get(LAST_OPENED_FILE)
    
    if args.autorun:
        runCLI(test_xml_path)
    else:
        runGUI(test_xml_path)

#--------------------------------------------------------------------#

if __name__ == '__main__':
    main()

