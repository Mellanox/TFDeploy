#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import re
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from EZRandomValueDescriptor import *
    
#############################################################################

class EZRandomSimpleHelper(QDialog):
    
    def __init__(self, weights, parent = None):
        super(EZRandomSimpleHelper, self).__init__(parent)
        self._weight_line_edits = {}
        self._weights = weights
        self._initGui()

    #--------------------------------------------------------------------#
                        
    def _initGui(self):
        self.setLayout(QGridLayout())
        row = 0
        for key, value in self._weights.iteritems():
            le = QLineEdit()
            le.setText(str(value))
            self._weight_line_edits[key] = le
            self.layout().addWidget(QLabel(key), row, 0)
            self.layout().addWidget(le, row, 1)
            row += 1
            
        self._b_ok = QPushButton("Ok")
        self._b_ok.clicked.connect(self.accept)
        self._b_cancel = QPushButton("Cancel")
        self._b_cancel.clicked.connect(self.reject)
        self.layout().addWidget(self._b_ok)
        self.layout().addWidget(self._b_cancel)
        
    #--------------------------------------------------------------------#
    
    def _validate(self):
        result = True
        for le in self._weight_line_edits.values():
            try:
                val = int(le.text())
                le.setStyleSheet("background-color: none")
            except ValueError:
                result = False
                le.setStyleSheet("background-color: #ffcccc")
                
        return result
    
    def _saveWeights(self):
        for key in self._weights.keys():
            le = self._weight_line_edits[key]
            self._weights[key] = int(le.text())

    def accept(self):
        if not self._validate():
            return
        
        self._saveWeights()
        return QDialog.accept(self)        
 
#############################################################################

class TagsCompleter(QCompleter):
 
    def __init__(self, parent, all_tags):
        QCompleter.__init__(self, all_tags, parent)
        self.all_tags = set(all_tags)
 
    #--------------------------------------------------------------------#
    
    def update(self, text_tags, completion_prefix):
        tags = list(self.all_tags)
        if completion_prefix in tags:
            tags.remove(completion_prefix)
        model = QStringListModel(tags, self)
        self.setModel(model)
 
        self.setCompletionPrefix(completion_prefix)
        #if completion_prefix.strip() != '':
        if True:
            self.complete()

#############################################################################

class EZRandomEdit(QLineEdit):
    
    def __init__(self, enums = None, parent = None):
        super(EZRandomEdit, self).__init__(parent)
        self._enums = enums
        self._ezrand = None
        self._initCompleter()
        self.textChanged.connect(self._textChanged)
         
    #--------------------------------------------------------------------#
    
    def _initCompleter(self):
        all_keys = []
        if self._enums != None:
            for enum in self._enums:
                all_keys.extend(enum.keys())

        completer = TagsCompleter(self, all_keys)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        #completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        completer.setWidget(self)
        QObject.connect(completer, SIGNAL('activated(QString)'), self._completeText)
        QObject.connect(self, SIGNAL('text_changed(PyQt_PyObject, PyQt_PyObject)'), completer.update)

    #--------------------------------------------------------------------#
    
    def _textChanged(self, text):
        
        text   = str(text)
        tags   = re.split(",|-", text)
        prefix = re.split(",|-", text[:self.cursorPosition()])[-1].strip()

        self.emit(SIGNAL('text_changed(PyQt_PyObject, PyQt_PyObject)'), tags, prefix)
 
    #--------------------------------------------------------------------#

    def _completeText(self, text):
        cursor_pos  = self.cursorPosition()
        before_text = str(self.text())[:cursor_pos]
        after_text  = str(self.text())[cursor_pos:]
        prefix_len  = len(re.split(",|-", before_text)[-1].strip())
        self.setText('%s%s%s' % (before_text[:cursor_pos - prefix_len], text, after_text))
        self.setCursorPosition(cursor_pos - prefix_len + len(text) + 2)

    #--------------------------------------------------------------------#
    
    def _createValueDescriptor(self):
        self.setStyleSheet("background-color: none")        
        self.setToolTip(QString(""))

        s = str(self.text())
        if len(s) == 0:
            self._ezrand = None
            return

        try:
            self._ezrand = EZRandomValueDescriptor.parse(s, enums = self._enums)
            self.setStyleSheet("background-color: none")
            self.setText(str(self._ezrand))
        except ValueDescriptorParseException as e:
            self._ezrand = None
            self.setStyleSheet("background-color: #ffcccc")
            self.setToolTip(QString(e.args[0]))
  
    #--------------------------------------------------------------------#
  
    def focusOutEvent(self, event):
        self._createValueDescriptor()
        super(EZRandomEdit, self).focusOutEvent(event)

    #--------------------------------------------------------------------#
    
#     def focusInEvent(self, event):
#         self._textChanged(self.text())
#         super(EZRandomEdit, self).focusInEvent(event)

    #--------------------------------------------------------------------#
    
    def refreshDescriptor(self):
        self._createValueDescriptor()
        
    #--------------------------------------------------------------------#
    
    def getDescriptor(self):
        return self._ezrand

#############################################################################            
            
class EZRandomWidget(QWidget):
    
    BASIC = 0
    ADVANCED = 1
    
    MODE_NAMES = ["Basic", "Advanced"]
    
    def __init__(self, allow_advanced_mode = False, base_widget_creator = None, parent = None, enums = None):
        super(EZRandomWidget, self).__init__(parent)
        self._enums = enums
        self._dual_mode = allow_advanced_mode and base_widget_creator != None 
        self._weights = {}
        if self._enums != None:
            for enum in self._enums:
                for key in enum:
                    self._weights[key] = 1

        self._initGui(base_widget_creator)

    #--------------------------------------------------------------------#
                        
    def _initGui(self, base_widget_creator):
        self.setLayout(QHBoxLayout())
        self._le_code = EZRandomEdit(self._enums)
        self._b_show_helper = QPushButton("...")
        self._b_show_helper.setMaximumWidth(30)
        self._b_show_helper.setCheckable(True)
        self._b_show_helper.clicked.connect(self._showHelper)
        
        self._b_mode = QPushButton()
        self._b_mode.resize(QSize(100, self._b_mode.height()))
        self._b_mode.clicked.connect(self._toggleMode)
        
        if base_widget_creator != None:
            self._base_widget = base_widget_creator(self, self._enums)
            self._mode = EZRandomWidget.BASIC
        else:
            self._base_widget = QWidget()
            self._mode = EZRandomWidget.ADVANCED

        self.layout().addWidget(self._base_widget, 1)
        self.layout().addWidget(self._le_code, 1)
        self.layout().addWidget(self._b_show_helper)
        
        if self._dual_mode:
            self.layout().addWidget(self._b_mode)
        self._setMode(self._mode)

            
        self.layout().setMargin(0)
        self.layout().setContentsMargins(0,0,0,0)
        
    #--------------------------------------------------------------------#
    
    def _setMode(self, mode):
        self._mode = mode
        self._b_mode.setText(EZRandomWidget.MODE_NAMES[1 - mode])
        self._base_widget.setVisible(mode == EZRandomWidget.BASIC)
        self._le_code.setVisible(mode == EZRandomWidget.ADVANCED)
        self._b_show_helper.setVisible(mode == EZRandomWidget.ADVANCED)
    
    #--------------------------------------------------------------------#
    
    def _toggleMode(self):
        self._setMode(1 - self._mode)
        
    #--------------------------------------------------------------------#
            
    def _showHelper(self):
        
        vd = self._le_code.getDescriptor()
        if vd != None:
            rand = vd.ezrand()            
            self._weights = {}
            for token in rand.tokens():
                self._weights[token.disp] = token.weight
        

        self._helper = EZRandomSimpleHelper(self._weights, self)
        rect = self._b_show_helper.geometry()
        point = self.mapToGlobal(rect.bottomLeft())
        self._helper.setGeometry(point.x(), point.y() + 30, self._helper.sizeHint().width(), self._helper.sizeHint().height())

        if self._helper.exec_() == QDialog.Accepted:
            st = ",".join(["%s: %u" % (key, value) for key, value in self._weights.iteritems()])
            self._le_code.setText(st)

        self._b_show_helper.setChecked(False)
 
 
    #--------------------------------------------------------------------#
    
    def getMode(self):
        return self._mode

    #--------------------------------------------------------------------#
    
    def setMode(self, mode):
        if self._dual_mode:
            self._setMode(mode)
        
    #--------------------------------------------------------------------#
 
    def getBasicText(self):
        return self._base_widget.currentText()
    
    #--------------------------------------------------------------------#
    
    def getAdvancedText(self):
        return self._le_code.text()
    
    #--------------------------------------------------------------------#
 
    def setBasicText(self, text):
        index = self._base_widget.findText(text)
        self._base_widget.setCurrentIndex(index)
    
    #--------------------------------------------------------------------#
    
    def setAdvancedText(self, text):
        self._le_code.text(setText(text))
        self._le_code.validate()
    
    #--------------------------------------------------------------------#

    def refreshDescriptor(self):
        self._le_code.refreshDescriptor()
        
    #--------------------------------------------------------------------#
            
    def getDescriptor(self):
        if self._mode == EZRandomWidget.BASIC:
            current_text = str(self._base_widget.currentText())
            for enum in self._enums:
                if current_text in enum:
                    value = enum[current_text]
            return FixedValueDescriptor(value)
        
        return self._le_code.getDescriptor()
        
################################################################################################################################################################################################
#
#                                                                         DEMO
#
################################################################################################################################################################################################

def create_combo_box(parent, enums):
    widget = QComboBox(parent)
    if enums != None:
        for enum in enums:
            widget.addItems(enum.keys())
    return widget

class DemoWidget(QWidget):
    
    def _monteCarlo(self):
        N = 100000
        
        print "Monte Carlo!"
        vd = self._getDesc()
        if vd == None:
            return
        
        try:
            ezrand = vd.ezrand()
            results = {}
            for token in ezrand.tokens():
                results[token.disp] = 0 
            
            for i in range(N):
                val = vd.next()
                for token in ezrand.tokens():
                    if val in token.range: 
                        results[token.disp] += 1
        except AttributeError:
            results = {}
            for i in range(N):
                val = vd.next()
                if val in results:
                    results[val] += 1
                else:
                    results[val] = 1
            
        print results
    
    def _getDesc(self):
        new_desc = self.ezrand_widget.getDescriptor()
        if str(new_desc) != str(self._desc):
            self._desc = new_desc
        return self._desc
        
    def _nextValue(self):
        desc = self._getDesc()
        if desc == None:
            self.l_value.setText("--")
        else:
            self.l_value.setText(str(desc.next()))

    def __init__(self, label, enums = None):
        self._desc = None
        
        super(DemoWidget, self).__init__()
        
        self.setLayout(QHBoxLayout())
        self.ezrand_widget = EZRandomWidget(allow_advanced_mode = True, base_widget_creator = create_combo_box, parent = self, enums = enums)
        
        b_monte_carlo = QPushButton("Monte Carlo!")
        b_monte_carlo.clicked.connect(self._monteCarlo)
        b_next_value = QPushButton("Next value")
        b_next_value.clicked.connect(self._nextValue)
        
        self.l_value = QLabel("??")
        self.l_label = QLabel(label + ":")
        self.l_label.setFixedWidth(50)
        
        self.layout().addWidget(self.l_label)
        self.layout().addWidget(self.ezrand_widget, 1)
        self.layout().addWidget(b_monte_carlo)
        self.layout().addWidget(b_next_value)
        self.layout().addWidget(self.l_value)

#         self.l_value.setFixedHeight(30)
#         self.l_label.setFixedHeight(30)

        self.layout().setMargin(0)
        #self.layout().setContentsMargins(0,0,0,0)
        #self.setContentsMargins(0,0,0,0)
        #self.setMinimumHeight(0)
        #self.setFixedHeight(50)
        

if __name__ == '__main__':
    app = QApplication([])
    prompt = QWidget()
    prompt.setLayout(QVBoxLayout())
    prompt.layout().addWidget(DemoWidget("Mode", [{"Background" : 0, "Nominal" : 1, "Performance" : 2}]))
    prompt.layout().addWidget(DemoWidget("Vals", [{"A" : 0, "B" : 1}]))
    prompt.layout().addStretch(1)
    prompt.resize(QSize(1024, 200))
    prompt.show()
    app.exec_()        









