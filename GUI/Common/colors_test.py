#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, os, random
from PyQt4.QtGui import QVBoxLayout, QMainWindow, QTreeWidgetItem, QIcon,\
    QMessageBox, QFileDialog, QWidget, QSplitter, QTreeWidget, QPushButton,\
    QLabel, QAction, QApplication, QHBoxLayout, QCheckBox, QLineEdit, QComboBox,\
    QBrush, QColor, QListWidget, QListWidgetItem
import colorsys
import itertools
from fractions import Fraction
import math

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

colors = ['#cc5151', '#7f3333', '#51cccc', '#337f7f', '#8ecc51', '#597f33', '#8e51cc', '#59337f', '#ccad51', '#7f6c33', '#51cc70', '#337f46', '#5170cc', '#33467f', '#cc51ad', '#7f336c', '#cc7f51', '#7f4f33', '#bccc51', '#757f33', '#60cc51', '#3c7f33', '#51cc9e', '#337f62', '#519ecc', '#33627f', '#6051cc', '#3c337f', '#bc51cc', '#75337f', '#cc517f', '#7f334f', '#cc6851', '#7f4133', '#cc9651', '#7f5e33', '#ccc451', '#7f7a33', '#a5cc51', '#677f33', '#77cc51', '#4a7f33', '#51cc59', '#337f37', '#51cc87', '#337f54', '#51ccb5', '#337f71', '#51b5cc', '#33717f', '#5187cc', '#33547f', '#5159cc', '#33377f', '#7751cc', '#4a337f', '#a551cc', '#67337f', '#cc51c4', '#7f337a', '#cc5196', '#7f335e', '#cc5168', '#7f3341', '#cc5d51', '#7f3a33', '#cc7451', '#7f4833', '#cc8a51', '#7f5633', '#cca151', '#7f6533', '#ccb851', '#7f7333', '#c8cc51', '#7d7f33', '#b1cc51', '#6e7f33', '#9acc51', '#607f33', '#83cc51', '#527f33', '#6ccc51', '#437f33', '#55cc51', '#357f33', '#51cc64', '#337f3e', '#51cc7b', '#337f4d', '#51cc92', '#337f5b', '#51cca9', '#337f69', '#51ccc0', '#337f78', '#51c0cc', '#33787f', '#51a9cc', '#33697f']


def main():
    app = QApplication(sys.argv)
    form = QListWidget()
    for color in colors:
        item = QListWidgetItem(color)
        item.setBackgroundColor(QColor(color))
        form.addItem(item)
    
    form.show()
    app.exec_()


if __name__ == "__main__":
    main()
