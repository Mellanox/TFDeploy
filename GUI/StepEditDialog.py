#!/usr/bin/python
# -*- coding: utf-8 -*-
from PyQt4.QtGui import QApplication, QDialog, QVBoxLayout, QComboBox, QWidget,\
    QPushButton, QDialogButtonBox
from Actions.Step import Step
from PyQt4.QtCore import Qt, QSize, QString

#############################################################################

class StepEditDialog(QDialog):
       
    def __init__(self, parent, step):
        super(StepEditDialog, self).__init__(parent)
        self._step = step
        self._initGui()
                 
    #--------------------------------------------------------------------#
    
    def _initGui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self._widgets = {}
        self._selected_widget = None
        self.cb_step_type = QComboBox()
        layout.addWidget(self.cb_step_type)
                
        if self._step is None:
            for step_class in Step.REGISTERED_STEPS.values():
                self.cb_step_type.addItem(step_class.NAME)
                w = step_class.GET_WIDGET()
                w.hide()
                values = [att.default_value for att in step_class.ATTRIBUTES]
                w.load(values)            
                self._widgets[step_class.NAME] = w
                layout.addWidget(w)
            self.cb_step_type.currentIndexChanged.connect(self._stepTypeChanged)
        else:
            self.cb_step_type.addItems(Step.REGISTERED_STEPS.keys())
            self.cb_step_type.setEnabled(False)
            index = self.cb_step_type.findText(QString(str(self._step.NAME)))
            self.cb_step_type.setCurrentIndex(index)
            w = self._step.getWidget()
            layout.addWidget(w)
        
        self._showStepProperties()
        layout.addStretch()
        
        ###################
        # Action Buttons: #
        ###################
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    #--------------------------------------------------------------------#
    
    def _showStepProperties(self):
        if self._selected_widget is not None:
            self._selected_widget.hide() 
        name = str(self.cb_step_type.currentText())
        self._selected_widget = self._widgets[name]
        self._selected_widget.show()
        
    #--------------------------------------------------------------------#
    
    def _stepTypeChanged(self):
        self._showStepProperties()
        
    #--------------------------------------------------------------------#
    
    def sizeHint(self):
        hint = QDialog.sizeHint(self)
        hint.setWidth(500)
        return hint

    #--------------------------------------------------------------------#
    
    def step(self):
        return self._step
        
    #--------------------------------------------------------------------#
    
    def accept(self, *args, **kwargs):
        if self._step is None:
            name = str(self.cb_step_type.currentText())
            step_class = Step.REGISTERED_STEPS[name] 
            self._step = step_class(self._selected_widget.values())
        else:
            self._selected_widget.save()
        return QDialog.accept(self, *args, **kwargs)
    
###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################
        
if __name__ == '__main__':

    app = QApplication([])
    prompt = StepEditDialog(None, None)
    prompt.show()
    app.exec_()
    print prompt.step()    
