#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from random import randint
from PyQt4.QtCore import *
from PyQt4.QtGui import *

################################################################################################################################################################################################

class TableDataItem(QTableWidgetItem):
    def __init__(self, data):
        super(TableDataItem, self).__init__(str(data))
        self._data = data
        
    def getData(self):
        return self._data

################################################################################################################################################################################################

class MyTableWidget(QTableWidget):
    def __init__(self, parent = None):
        super(MyTableWidget, self).__init__(parent)
        self.shapers = []
        
    def addShaper(self, shaper):
        self.shapers.append(shaper)
        
    def setData(self, data, horizontal, vertical):
        print horizontal
        print vertical
        print data
        
        num_rows = len(vertical)
        num_cols = len(horizontal)
        
        self.setRowCount(num_rows)
        self.setColumnCount(num_cols)
        
        for row in range(num_rows):
            for col in range(num_cols):
                item = TableDataItem(data[row][col])
                for shaper in self.shapers:
                    shaper(item, self)
                self.setItem(row, col, item)

        self.setHorizontalHeaderLabels(horizontal)
        self.setVerticalHeaderLabels(vertical)
        
################################################################################################################################################################################################
#
#                                                                         DEMO
#
################################################################################################################################################################################################


def color_below_100(item, widget):
    if item.getData() < 100:
        item.setForeground(Qt.red)
    
table = None
max_num_rows = 10
max_num_cols = 10
MAX_VALUE = 1000

def rand_header():
    return "%c%c" % (randint(ord('A'), ord('Z')), randint(ord('A'), ord('Z')))

def xxx():
    num_rows = randint(0, max_num_rows)
    num_cols = randint(0, max_num_cols)
    
    horizontal = []
    vertical = []
    data = []
    
    print "%u %u" % (num_rows, num_cols)
    for col in range(num_cols):
        horizontal.append(rand_header())
    
    for row in range(num_rows):
        vertical.append(rand_header())
        row = []
        data.append(row)
        for col in range(num_cols):
            row.append(randint(0, MAX_VALUE))
        
    table.setData(data, horizontal, vertical)
        
if __name__ == '__main__':
    app = QApplication([])
    prompt = QWidget()
    prompt.setLayout(QVBoxLayout())
    table = MyTableWidget()
    table.addShaper(color_below_100)
    
    button = QPushButton("Push me")
    button.clicked.connect(xxx)

    prompt.layout().addWidget(table)
    prompt.layout().addWidget(button)

    prompt.resize(QSize(800, 600))
    prompt.show()
    #prompt.setData([[7,0,1,2],[8,3,4,5]], ["R","F","G","H"], ["S","T"])
    app.exec_()







