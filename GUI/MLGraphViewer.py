#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
This demo demonstrates how to embed a matplotlib (mpl) plot 
into a PyQt4 GUI application, including:

* Using the navigation toolbar
* Adding data to the plot
* Dynamically modifying the plot's properties
* Processing mpl events
* Saving the plot to a file from a menu

The main goal is to serve as a basis for developing rich PyQt GUI
applications featuring mpl plots (using the mpl OO API).

Eli Bendersky (eliben@gmail.com)
License: this code is in the public domain
Last modified: 19.01.2009
"""
import sys, os, random
from PyQt4.QtGui import QVBoxLayout, QMainWindow, QTreeWidgetItem, QIcon,\
    QMessageBox, QFileDialog, QWidget, QSplitter, QTreeWidget, QPushButton,\
    QLabel, QAction, QApplication, QHBoxLayout, QCheckBox, QLineEdit, QComboBox,\
    QBrush, QColor

import matplotlib
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt4.QtCore import Qt, QString, SIGNAL

###############################################################################

class GraphDesc(object):
    def __init__(self, graph_type, ymax):
        self.graph_type = graph_type
        self.ymax = ymax

###############################################################################

class Graph(object):
    
    TYPE_NORMAL = 0
    TYPE_RATE = 1
    TYPE_DELTA = 2

    # -------------------------------------------------------------------- #
    
    GRAPH_KINDS = {}
    
    @staticmethod
    def getGraphDesc(csv_path):
        kind = os.path.basename(csv_path).split("-")[0]
        if kind in ["timeline.csv"]:
            ymax = 1
            graph_type = Graph.TYPE_DELTA
        elif kind in ["STIME", "UTIME"]:
            ymax = 1600
            graph_type = Graph.TYPE_RATE
        elif kind in ["RDTA", "TDTA"]:
            ymax = 150000
            graph_type = Graph.TYPE_RATE
        elif kind in ["GPU"]:
            ymax = 300
            graph_type = Graph.TYPE_NORMAL
        else:
            return None
        return GraphDesc(graph_type, ymax)

        
    # -------------------------------------------------------------------- #
        
    def __init__(self, label, csv_path, graph_type, start_time, color, ymax=None):
        self._label = label
        self._csv_path = csv_path
        self._type = graph_type
        self._start_time = start_time
        self._color = color
        self._ymax = ymax
        self._ax = None
        self._x = []
        self._y = []
        self._readData()
    
    # -------------------------------------------------------------------- #
        
    def _readData(self):
        i = 0
        last_val = None
        last_timestamp = None
        with open(self._csv_path, "r") as csv:
            for line in csv:
                parts = line.replace(" ","").split(",")
                try:        
                    timestamp = float(parts[0]) - self._start_time
                    val = float(parts[1])
                except:
                    print "Error on graph: %s: %u \"%s\." % (os.path.basename(self._csv_path), i, line)
                    raise
                i += 1

                if self._type == Graph.TYPE_NORMAL:
                    self._x.append(timestamp)
                    self._y.append(val)
                elif self._type == Graph.TYPE_RATE:                
                    rate = 0 if last_val is None else (val - last_val) / (timestamp - last_timestamp)
                    if rate > 1000000:
                        print "Error on graph: %s: %u \"%s\." % (os.path.basename(self._csv_path), i, line)
                        sys.exit(1)
                        
                    last_timestamp = timestamp
                    last_val = val
                    self._x.append(timestamp)
                    self._y.append(rate)
                elif self._type == Graph.TYPE_DELTA:                
                    self._x.append(timestamp - 0.01)
                    self._x.append(timestamp)
                    self._x.append(timestamp + 0.01)
                    self._y.append(0)
                    self._y.append(1)
                    self._y.append(0)    

    # -------------------------------------------------------------------- #
    
    def _createAx(self, fig, host):
        self._ax = host.twinx()
        #self._ax.set_ylabel(self._label, color=self._color)
        self._ax.tick_params('y', colors=self._color)
        #self._ax.axes.get_yaxis().set_ticklabels([])        
        return host

    # -------------------------------------------------------------------- #
    
    def color(self):
        return self._color
    
    # -------------------------------------------------------------------- #
    
    def plot(self, fig, host, pos):
        if self._ax is None:
            host = self._createAx(fig, host)
        
        if pos > 1.01:
            self._ax.spines["right"].set_position(("axes", pos))
            
        if self._ymax is not None:
            self._ax.set_ylim(0, self._ymax)
        else:
            self._ax.set_ylim(0)
                        
        self._ax.plot(self._x, self._y, self._color)
        self._ax.axes.get_yaxis().set_visible(True)
        return fig, host
    
    # -------------------------------------------------------------------- #
    
    def clear(self):
        self._ax.axes.get_yaxis().set_visible(False)
        self._ax.clear()
        

###############################################################################

class GraphFileTreeWidgetItem(QTreeWidgetItem):
    
    def __init__(self, parent, csv_path):
        QTreeWidgetItem.__init__(self, parent)
        
        self._csv_path = csv_path
        self.widget = QWidget()
        self.widget.setLayout(QHBoxLayout())
        self.cb_enabled = QCheckBox()
        self.le_label = QLineEdit("")
        self.cb_graph_type = QComboBox()
        self.cb_graph_type.addItems(["NORMAL", "RATE", "DELTA"])
        
        self.widget.layout().addWidget(self.cb_enabled)
        self.widget.layout().addWidget(QLabel(os.path.basename(csv_path)))
        self.widget.layout().addWidget(QLabel("Label:"))
        self.widget.layout().addWidget(self.le_label)
        self.widget.layout().addWidget(QLabel("Type:"))
        self.widget.layout().addWidget(self.cb_graph_type)
        
        self.treeWidget().setItemWidget(self, 0, self.widget)        


###############################################################################

class MLGraphViewer(QMainWindow):
    
    COLORS = [QColor(0xff, 0x00, 0x00),
              QColor(0xff, 0x80, 0x00),
              QColor(0xbf, 0xff, 0x00),
              QColor(0x00, 0xff, 0x00),
              QColor(0x00, 0xff, 0xbf),
              QColor(0x00, 0xbf, 0xff),
              QColor(0x80, 0x00, 0xff),
              QColor(0xbf, 0x00, 0xff),
              QColor(0xff, 0x00, 0xff)]
    
    # -------------------------------------------------------------------- #
        
    def __init__(self, base_dir, parent=None):
        QMainWindow.__init__(self, parent)

        self._base_dir = base_dir
        self._graphs = {}
        self._handleChanges = True
        
        self.setWindowTitle('ML Graph Viewer')

        self.create_menu()
        self.create_main_frame()
        self.create_status_bar()

    # -------------------------------------------------------------------- #
    
    def _getNextColor(self):
        index = len(self._graphs)
        return MLGraphViewer.COLORS[index]
        
    # -------------------------------------------------------------------- #
    
    def _getOrCreateGraph(self, csv_path):
        csv_path = str(csv_path)
        if csv_path in self._graphs:
            return self._graphs[csv_path]
        
        label = csv_path #
        desc = Graph.getGraphDesc(csv_path)        
        color = self._getNextColor()
        graph = Graph(label, csv_path, desc.graph_type, 0, str(color.name()), desc.ymax)
        self._graphs[csv_path] = graph
        return graph
            
    # -------------------------------------------------------------------- #

    def _onTreeItemChanged(self, item):
        if not self._handleChanges:
            return 
        
        csv_path = item.data(0, Qt.UserRole).toString()
        print "%s checked: %u" % (csv_path, item.checkState(0))
        graph = self._getOrCreateGraph(csv_path)
        if item.checkState(0) == Qt.Checked:
            self.fig, self.host = graph.plot(self.fig, self.host, 1.0)#self.pos)
            self.pos += 0.08
            self.num_plots += 1
            item.setBackground(0, QBrush(QColor(graph.color())))    
        else:
            graph.clear()
            self.pos -= 0.08
            self.num_plots -= 1
            item.setBackground(0, QBrush())    

        self.fig.tight_layout(pad=0)
        self.canvas.draw()
    
    # -------------------------------------------------------------------- #
    
    def _refresh(self):
        self._handleChanges = False
        self._tree.clear()
        self._loadDir(self._base_dir, self._tree)
        self._handleChanges = True
    
    # -------------------------------------------------------------------- #
    
    def _onRefreshClicked(self):
        self._refresh()
        
    # -------------------------------------------------------------------- #
    
    def _loadDir(self, base_path, tree):
        for element in os.listdir(base_path):
            path = os.path.join(base_path, element)
            if (not os.path.isdir(path)) and (not path.endswith(".csv")):
                continue
            
            if os.path.isdir(path):
                parent_itm = QTreeWidgetItem(tree, [element])
                self._loadDir(path, parent_itm)
                if parent_itm.childCount() == 0:
                    parent = parent_itm.parent()
                    root = parent_itm.treeWidget().invisibleRootItem()
                    (parent or root).removeChild(parent_itm)
                else:                                        
                    parent_itm.setIcon(0, QIcon("/usr/share/icons/ubuntu-mono-light/places/16/folder-home.svg"))
                    parent_itm.setExpanded(True)
            else:
                if Graph.getGraphDesc(path) is None:
                    continue
                # item = GraphFileTreeWidgetItem(tree, element)
                item = QTreeWidgetItem(tree, [element])
                item.setData(0, Qt.UserRole, path)
                item.setCheckState(0, Qt.Unchecked)
                
    # -------------------------------------------------------------------- #

    def save_plot(self):
        file_choices = "PNG (*.png)|*.png"
        
        path = unicode(QFileDialog.getSaveFileName(self, 
                        'Save file', '', 
                        file_choices))
        if path:
            self.canvas.print_figure(path, dpi=self.dpi)
            self.statusBar().showMessage('Saved to %s' % path, 2000)
    
    # -------------------------------------------------------------------- #
    
    def on_about(self):
        msg = """ View one or more graphs on a joined canvas.
            
            Many thanks to Eli Bendersky from Google for the PyPlot skeleton. 
        """
        QMessageBox.about(self, "ML Graph Viewer", msg.strip())
    
    # -------------------------------------------------------------------- #
    
    def on_pick(self, event):
        # The event received here is of the type
        # matplotlib.backend_bases.PickEvent
        #
        # It carries lots of information, of which we're using
        # only a small amount here.
        # 
        box_points = event.artist.get_bbox().get_points()
        msg = "You've clicked on a bar with coords:\n %s" % box_points
        
        QMessageBox.information(self, "Click!", msg)

    # -------------------------------------------------------------------- #
    
    def _openCSVFile(self, base_dir):
        selfilter = QString("CSV (*.csv)")
        file_path = QFileDialog.getOpenFileName(None, 'Open File', '/', 
                                                "All files (*.*);;CSV (*.csv)", 
                                                selfilter)
        return file_path
    
    # -------------------------------------------------------------------- #

    def create_main_frame(self):
        self.main_frame = QWidget()
        
        # Create the mpl Figure and FigCanvas objects. 
        # 5x4 inches, 100 dots-per-inch
        #
        #self.dpi = 100
        self.fig = Figure() #(5.0, 4.0), dpi=self.dpi)
        self.host = self.fig.add_subplot(1, 1, 1)
        self.host.axes.get_yaxis().set_visible(False)
        self.pos = 0.9
        self.num_plots = 0
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setParent(self.main_frame)
        
        # Bind the 'pick' event for clicking on one of the bars
        #
        self.canvas.mpl_connect('pick_event', self.on_pick)
        
        # Create the navigation toolbar, tied to the canvas
        #
        self.mpl_toolbar = NavigationToolbar(self.canvas, self.main_frame)
        
#         self.grid_cb = QCheckBox("Show &Grid")
#         self.grid_cb.setChecked(False)
#         self.connect(self.grid_cb, SIGNAL('stateChanged(int)'), self.on_draw)
        
#         slider_label = QLabel('Bar width (%):')
#         self.slider = QSlider(Qt.Horizontal)
#         self.slider.setRange(1, 100)
#         self.slider.setValue(20)
#         self.slider.setTracking(True)
#         self.slider.setTickPosition(QSlider.TicksBothSides)
#         self.connect(self.slider, SIGNAL('valueChanged(int)'), self.on_draw)

        splitter = QSplitter()
                        
        self._tree = QTreeWidget(splitter)
        self._tree.setHeaderLabel("Files")
        self._loadDir(self._base_dir, self._tree)
        self._tree.itemChanged.connect(self._onTreeItemChanged)
        
        self.b_refresh = QPushButton("Refresh")
        self.b_refresh.clicked.connect(self._onRefreshClicked)
        
        file_select_pane = QWidget(splitter)
        file_select_pane.setLayout(QVBoxLayout())
        file_select_pane.layout().addWidget(self._tree)
        file_select_pane.layout().addWidget(self.b_refresh)
        
        canvas_pane = QWidget(splitter) 
        canvas_pane.setLayout(QVBoxLayout())
        canvas_pane.layout().addWidget(self.canvas)
        canvas_pane.layout().addWidget(self.mpl_toolbar)
        
        self.setCentralWidget(splitter)
    
    def create_status_bar(self):
        self.status_text = QLabel("")
        self.statusBar().addWidget(self.status_text, 1)
        
    def create_menu(self):        
        self.file_menu = self.menuBar().addMenu("&File")
        
        load_file_action = self.create_action("&Save plot",
            shortcut="Ctrl+S", slot=self.save_plot, 
            tip="Save the plot")
        quit_action = self.create_action("&Quit", slot=self.close, 
            shortcut="Ctrl+Q", tip="Close the application")
        
        self.add_actions(self.file_menu, 
            (load_file_action, None, quit_action))
        
        self.help_menu = self.menuBar().addMenu("&Help")
        about_action = self.create_action("&About", 
            shortcut='F1', slot=self.on_about, 
            tip='About the demo')
        
        self.add_actions(self.help_menu, (about_action,))

    def add_actions(self, target, actions):
        for action in actions:
            if action is None:
                target.addSeparator()
            else:
                target.addAction(action)

    def create_action(  self, text, slot=None, shortcut=None, 
                        icon=None, tip=None, checkable=False, 
                        signal="triggered()"):
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon(":/%s.png" % icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            self.connect(action, SIGNAL(signal), slot)
        if checkable:
            action.setCheckable(True)
        return action

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

def main():
    if len(sys.argv) >= 2:
        base_dir = sys.argv[1]
    else:
        base_dir = "."
    app = QApplication(sys.argv)
    form = MLGraphViewer(base_dir)
    form.show()
    app.exec_()


if __name__ == "__main__":
    main()
