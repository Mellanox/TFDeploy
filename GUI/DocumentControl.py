
import sys
import os
from PyQt4.QtCore import *
from PyQt4.QtGui import *

class DocumentControl(object):
    
    def __init__(self, parent, file_filters, default_folder):
        self._parent = parent
        self._file_filters = file_filters
        self._default_folder = default_folder
        self._modified = False
        self._file_path = None    
    
    #--------------------------------------------------------------------#
     
    def _promptModified(self):
        if not self._modified:
            return True
        
        msgBox = QMessageBox(self._parent)
        msgBox.setText("The document has been modified.")
        msgBox.setInformativeText("Do you want to save your changes?")
        save_button = QPushButton("Save")
        dont_save_button = QPushButton("Don't save")
        cancel_button = QPushButton("Cancel")
        msgBox.addButton(cancel_button, QMessageBox.YesRole)
        msgBox.addButton(dont_save_button, QMessageBox.YesRole)
        msgBox.addButton(save_button, QMessageBox.YesRole)
        msgBox.setDefaultButton(save_button)
        msgBox.exec_()
        
        if msgBox.clickedButton() == save_button:
            self._saveOrSaveAs()
            return True
        elif msgBox.clickedButton() == dont_save_button:
            return True
        elif msgBox.clickedButton() == cancel_button:
            return False
        else:
            pass                        
                   
    #--------------------------------------------------------------------#
    
    def _doSave(self, content):
        with open(self._file_path, "w") as file:
            file.write(content)
        self._modified = False
                           
    #--------------------------------------------------------------------#                           
    
    def _doSaveAs(self, content):
        file_path = QFileDialog(self._parent).getSaveFileName(self._parent, "Save File", self._default_folder, self._file_filters)
        if len(file_path) == 0:
            return
        
        self._file_path = file_path 
        self._doSave(content)

    #--------------------------------------------------------------------#                

    def _saveOrSaveAs(self, content):
        if self._file_path == None:
            self._doSaveAs(content)
        else:
            self._doSave(content)

    #--------------------------------------------------------------------#
        
    def new(self):
        if not self._promptModified():
            return
        
        self._file_path = None
        self._modified = False
        
    #--------------------------------------------------------------------#
    
    def setModified(self, value):
        self._modified = value
                
    #--------------------------------------------------------------------#        
    
    def save(self, content):
        self._saveOrSaveAs(content)
        
    #--------------------------------------------------------------------#
            
    def load(self):
        if not self._promptModified():
            return None
        
        file_path = QFileDialog(self._parent).getOpenFileName(self._parent, "Load File", self._default_folder, self._file_filters)
        if len(file_path) == 0 or not os.path.isfile(file_path):
            return None
        
        self._file_path = file_path
        self._modified = False
        with open(self._file_path, "r") as file:
            content = file.read()
            
        return content        
      
    #--------------------------------------------------------------------#
    
    def close(self):
        return self._promptModified()
