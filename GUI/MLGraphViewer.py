#!/usr/bin/python
# -*- coding: utf-8 -*-
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
        
    def __init__(self, label, csv_path, graph_type, ymax=None):
        self._label = label
        self._csv_path = csv_path
        self._type = graph_type
        self._ymax = ymax
        self._color = None
        self._ax = None
        self._x = []
        self._y = []
        self._readData()
    
    # -------------------------------------------------------------------- #
        
    def _readData(self):
        ####################################
        # Get start time from timeline.csv #
        ####################################
        dirname = os.path.dirname(self._csv_path)
        timeline_path = os.path.join(dirname, "timeline.csv")
        if os.path.isfile(timeline_path):
            with open(timeline_path) as timeline:
                timeline.readline() # Skip 1st step
                start_time = float(timeline.readline().split(",")[0])
        else:
            start_time = 0
        
        ####################
        # Read graph data: #
        ####################
        i = 0
        last_val = None
        last_timestamp = None
        with open(self._csv_path, "r") as csv:
            for line in csv:
                parts = line.replace(" ","").split(",")
                try:        
                    timestamp = float(parts[0]) - start_time
                    if timestamp < 0:
                        continue
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
                    self._x.append(timestamp - 0.0)
                    self._x.append(timestamp)
                    self._x.append(timestamp + 0.0)
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
    
    def setColor(self, val):
        self._color = val
        
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
        
    # -------------------------------------------------------------------- #
    
    def scaleTo(self, host):
        base_ymax = self._ymax if self._ymax is not None else max(self._y)
        base_ymin = 0
        host_ymin, host_ymax = host.get_ylim()
        yrange = base_ymax - base_ymin
        ymax = yrange * host_ymax # host_ymax is between 0 and 1
        ymin = yrange * host_ymin # host_ymax is between 0 and 1
        print yrange
        print (host_ymin, host_ymax)
        print (ymin, ymax)
        self._ax.set_ylim(ymin, ymax)
        

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
    
    COLORS = ["#ff0000", "#ff8000", "#bfff00", "#00ff00", "#00ffbf", "#00bfff", "#8000ff", "#bf00ff", "#ff00ff",    
              "#cc5151", "#7f3333", "#51cccc", "#337f7f", "#8ecc51", "#597f33", "#8e51cc", "#59337f", "#ccad51", "#7f6c33", "#51cc70", "#337f46", "#5170cc", "#33467f", "#cc51ad", "#7f336c", "#cc7f51", "#7f4f33", "#bccc51", "#757f33", "#60cc51", "#3c7f33", "#51cc9e", "#337f62", "#519ecc", "#33627f", "#6051cc", "#3c337f", "#bc51cc", "#75337f", "#cc517f", "#7f334f", "#cc6851", "#7f4133", "#cc9651", "#7f5e33", "#ccc451", "#7f7a33", "#a5cc51", "#677f33", "#77cc51", "#4a7f33", "#51cc59", "#337f37", "#51cc87", "#337f54", "#51ccb5", "#337f71", "#51b5cc", "#33717f", "#5187cc", "#33547f", "#5159cc", "#33377f", "#7751cc", "#4a337f", "#a551cc", "#67337f", "#cc51c4", "#7f337a", "#cc5196", "#7f335e", "#cc5168", "#7f3341", "#cc5d51", "#7f3a33", "#cc7451", "#7f4833", "#cc8a51", "#7f5633", "#cca151", "#7f6533", "#ccb851", "#7f7333", "#c8cc51", "#7d7f33", "#b1cc51", "#6e7f33", "#9acc51", "#607f33", "#83cc51", "#527f33", "#6ccc51", "#437f33", "#55cc51", "#357f33", "#51cc64", "#337f3e", "#51cc7b", "#337f4d", "#51cc92", "#337f5b", "#51cca9", "#337f69", "#51ccc0", "#337f78", "#51c0cc", "#33787f", "#51a9cc", "#33697f"]
    COLOR_MAP = dict((c, True) for c in COLORS)

    # -------------------------------------------------------------------- #

    def _onXlimsChange(self, axes):
        print "updated xlims: ", axes.get_xlim()
    
    # -------------------------------------------------------------------- #
    
    def _onYlimsChange(self, axes):
        print "updated ylims: ", axes.get_ylim()
        for graph in self._graphs.values():
            graph.scaleTo(axes)
        self.fig.tight_layout(pad=0)
        
   
    # -------------------------------------------------------------------- #
        
    def __init__(self, dirs, parent=None):
        QMainWindow.__init__(self, parent)

        self._dirs = dirs
        self._graphs = {}
        self._handleChanges = True
        
        self.setWindowTitle('ML Graph Viewer')

        self.create_menu()
        self.create_main_frame()
        self.create_status_bar()

    # -------------------------------------------------------------------- #
    
    def _getNextColor(self):
        for c in MLGraphViewer.COLORS:
            if MLGraphViewer.COLOR_MAP[c]:
                return c
        raise Exception("No more available colors.")
        
    # -------------------------------------------------------------------- #
    
    def _getOrCreateGraph(self, csv_path):
        csv_path = str(csv_path)
        if csv_path in self._graphs:
            graph = self._graphs[csv_path]
        else:
            label = csv_path #
            desc = Graph.getGraphDesc(csv_path)        
            graph = Graph(label, csv_path, desc.graph_type, desc.ymax)
            self._graphs[csv_path] = graph
        return graph
            
    # -------------------------------------------------------------------- #

    def _onTreeItemChanged(self, item):
        if not self._handleChanges:
            return 
        
        self._handleChanges = False
        csv_path = item.data(0, Qt.UserRole).toString()
        graph = self._getOrCreateGraph(csv_path)
        if item.checkState(0) == Qt.Checked:
            ###################
            # Allocate color: #
            ###################
            color = self._getNextColor()
            graph.setColor(color)
            MLGraphViewer.COLOR_MAP[graph.color()] = False
            
            self.fig, self.host = graph.plot(self.fig, self.host, 1.0)#self.pos)
            self.pos += 0.08
            self.num_plots += 1
            item.setBackground(0, QBrush(QColor(graph.color())))
        else:
            ###############
            # Free color: #
            ###############
            if graph.color() is not None:
                MLGraphViewer.COLOR_MAP[graph.color()] = True
            
            graph.clear()
            self.pos -= 0.08
            self.num_plots -= 1
            item.setBackground(0, QBrush())

        self.fig.tight_layout(pad=0)
        self.canvas.draw()
        self._handleChanges = True
    
    # -------------------------------------------------------------------- #
    
    def _refresh(self):
        self._handleChanges = False
        self._tree.clear()
        for dir in self._dirs:
            name = os.path.basename(os.path.normpath(dir))
            top_level_item = QTreeWidgetItem(self._tree, [name])
            self._loadDir(dir, top_level_item)
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
                    # parent_itm.setExpanded(True)
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
        self.fig.tight_layout(pad=0)

        #self.host.callbacks.connect('xlim_changed', self._onXlimsChange)
        #self.host.callbacks.connect('ylim_changed', self._onYlimsChange)        
        
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
        self._refresh()
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
        base_dir = sys.argv[1:]
    else:
        base_dir = ["."]
    app = QApplication(sys.argv)
    form = MLGraphViewer(base_dir)
    form.show()
    app.exec_()


if __name__ == "__main__":
    main()
