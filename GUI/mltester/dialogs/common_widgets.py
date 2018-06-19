'''
Created on Jun 18, 2018

@author: eladw
'''
from PyQt4.Qt import QWidget, QPushButton, QLineEdit, QGridLayout, QVBoxLayout,\
    QTabWidget, QIcon, QAction, QSize, QToolBar, QHBoxLayout, QLabel
from commonpylib.gui.EZRandomWidget import EZRandomWidget
import os


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
    def __init__(self, mnt, icon_path, text, shortcut, handler, enabled=True, checkable=False, checked=False):
        super(ActionWithButton, self).__init__(QIcon(icon_path), text, mnt.menu)
        self.setShortcut(shortcut)
        #self.setStatusTip(text)
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
