#!/usr/bin/python
# -*- coding: utf-8 -*-

from random import randint
from PyQt4.QtCore import *
from PyQt4.QtGui import *

###############################################################################

LOG_LEVEL_FATAL = 0
LOG_LEVEL_ERROR = 1
LOG_LEVEL_WARNING = 2
LOG_LEVEL_INFO = 3
LOG_LEVEL_DEBUG = 4
LOG_LEVEL_NONE = 5

LogColorsForLevel = ["purple", "red", "orange", None, None, None]
LogLevelNames = ["FATAL", "ERROR", "WARNING", "INFO", "DEBUG", "NONE"] 
        
###############################################################################

class LogWidget(QMdiSubWindow):
    
    def __init__(self, log_id, title = None, parent = None):
        super(LogWidget, self).__init__(parent)
        if title is None:
            title = log_id
        self._initGui(title)
        
    #--------------------------------------------------------------------#
    
    def _initGui(self, title):
        self.setWindowTitle(str(title))
        self._te_log = QPlainTextEdit()
        self._te_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.layout().addWidget(self._te_log)
        
    #--------------------------------------------------------------------#
    
    def append(self, line, log_level = LOG_LEVEL_INFO):
        color = LogColorsForLevel[log_level]
        if color is not None: 
            line = "<font color='%s'>%s</font>" % (color, line)
        self._te_log.setReadOnly(True)
        self._te_log.appendHtml(line)
        scrollbar = self._te_log.verticalScrollBar() 
        scrollbar.setValue(scrollbar.maximum())            

###############################################################################

class MultiLogWidget(QMdiArea):
    
    GLOBAL_LOG = object()
    SUB_WINDOW_DEFAULT_RATIO_X = 0.8
    SUB_WINDOW_DEFAULT_RATIO_Y = 0.8
    CASCADE_SKIP_PIXELS_X = 10 
    CASCADE_SKIP_PIXELS_Y = 25
    
    #--------------------------------------------------------------------#
    
    def __init__(self, parent = None):
        super(MultiLogWidget, self).__init__(parent)
        self.logs_ = {} 
        self.cascade_x_id = 0
        self.cascade_y_id = 0
        
        self._initGui()
        
    #--------------------------------------------------------------------#
    
    def _initGui(self):
        pass
        
    #--------------------------------------------------------------------#
    
    def _getNextWindowPosition(self):
        x = self.cascade_x_id * MultiLogWidget.CASCADE_SKIP_PIXELS_X
        y = self.cascade_y_id * MultiLogWidget.CASCADE_SKIP_PIXELS_Y
        if y > (1 - MultiLogWidget.SUB_WINDOW_DEFAULT_RATIO_X) * self.height():
            y = 0
            self.cascade_y_id = 0
        if x > (1 - MultiLogWidget.SUB_WINDOW_DEFAULT_RATIO_Y) * self.width():
            x = 0
            self.cascade_x_id = 0
        self.cascade_x_id += 1
        self.cascade_y_id += 1
        return QPoint(x,y)
        
    #--------------------------------------------------------------------#
    
    def _getOrCreateLog(self, log_id, title):
        if log_id in self.logs_:
            return self.logs_[log_id]
        log = LogWidget(log_id, title)
        self.logs_[log_id] = log
        return log 
    
    #--------------------------------------------------------------------#
    
    def _removeLog(self, log_id):
        if log_id in self.logs_:
            return self.logs_.pop(log_id)
        return None
        
    #--------------------------------------------------------------------#
    
    def open(self, log_id = GLOBAL_LOG, title = None):
        log = self._getOrCreateLog(log_id, title)
        if not log in self.subWindowList():
            pos = self._getNextWindowPosition()
            size = QSize(self.width() * MultiLogWidget.SUB_WINDOW_DEFAULT_RATIO_X, 
                         self.height() * MultiLogWidget.SUB_WINDOW_DEFAULT_RATIO_Y)
            self.addSubWindow(log)
            log.resize(size)
            log.move(pos)
            
        log.show()
        return log 

    #--------------------------------------------------------------------#
    
    def close(self, log_id = GLOBAL_LOG):
        log = self._removeLog(log_id)
        if log is not None:
            self.removeSubWindow(log)
        
    #--------------------------------------------------------------------#
    
    def log(self, line, log_id = GLOBAL_LOG, log_level = LOG_LEVEL_INFO):
        log = self.open(log_id)
        log.append(line, log_level)
        
###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

x = 0
log_id = 0

#--------------------------------------------------------------------#

def test(): 
    global x
    global log_id
    
    log_level = randint(0, 5)
    mlog.log("%s Line #%u" % (LogLevelNames[log_level], x), log_id, log_level)
    x += 1
    log_id = (log_id + 1) % 30

#--------------------------------------------------------------------#
       
if __name__ == '__main__':
    app = QApplication([])
    prompt = QWidget()
    prompt.setLayout(QVBoxLayout())
    mlog = MultiLogWidget()
    
    button = QPushButton("Push me")
    button.clicked.connect(test)

    prompt.layout().addWidget(mlog)
    prompt.layout().addWidget(button)

    prompt.resize(QSize(800, 600))
    prompt.show()
    #prompt.setData([[7,0,1,2],[8,3,4,5]], ["R","F","G","H"], ["S","T"])
    app.exec_()







