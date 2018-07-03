#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys, os
from PyQt4.Qt import QVBoxLayout, QMainWindow, QTreeWidgetItem, QIcon,\
    QMessageBox, QFileDialog, QWidget, QSplitter, QTreeWidget, QPushButton,\
    QLabel, QAction, QApplication, QHBoxLayout, QBrush, QColor, QSpinBox, Qt, \
    QString, SIGNAL

COLORS = ["#ff0000", "#ff8000", "#bfff00", "#00ff00", "#00ffbf", "#00bfff", "#8000ff", "#bf00ff", "#ff00ff",
          "#cc5151", "#7f3333", "#51cccc", "#337f7f", "#8ecc51", "#597f33", "#8e51cc", "#59337f", "#ccad51",
          "#7f6c33", "#51cc70", "#337f46", "#5170cc", "#33467f", "#cc51ad", "#7f336c", "#cc7f51", "#7f4f33",
          "#bccc51", "#757f33", "#60cc51", "#3c7f33", "#51cc9e", "#337f62", "#519ecc", "#33627f", "#6051cc",
          "#3c337f", "#bc51cc", "#75337f", "#cc517f", "#7f334f", "#cc6851", "#7f4133", "#cc9651", "#7f5e33",
          "#ccc451", "#7f7a33", "#a5cc51", "#677f33", "#77cc51", "#4a7f33", "#51cc59", "#337f37", "#51cc87",
          "#337f54", "#51ccb5", "#337f71", "#51b5cc", "#33717f", "#5187cc", "#33547f", "#5159cc", "#33377f",
          "#7751cc", "#4a337f", "#a551cc", "#67337f", "#cc51c4", "#7f337a", "#cc5196", "#7f335e", "#cc5168",
          "#7f3341", "#cc5d51", "#7f3a33", "#cc7451", "#7f4833", "#cc8a51", "#7f5633", "#cca151", "#7f6533",
          "#ccb851", "#7f7333", "#c8cc51", "#7d7f33", "#b1cc51", "#6e7f33", "#9acc51", "#607f33", "#83cc51",
          "#527f33", "#6ccc51", "#437f33", "#55cc51", "#357f33", "#51cc64", "#337f3e", "#51cc7b", "#337f4d",
          "#51cc92", "#337f5b", "#51cca9", "#337f69", "#51ccc0", "#337f78", "#51c0cc", "#33787f", "#51a9cc",
          "#33697f"]
COLOR_MAP = dict((c, True) for c in COLORS)

label_colors = {}
tl_graph_count = 0

###############################################################################

class Section(object):
    def __init__(self, label):
        self.label = label
        self.x = []
        self.y = []

###############################################################################

class GraphDesc(object):
    def __init__(self, graph_type, ymax, yshift, line_width, marker, zorder):
        self.graph_type = graph_type
        self.ymax = ymax
        self.yshift = yshift
        self.line_width = line_width
        self.marker =  marker
        self.zorder = zorder

###############################################################################

class Graph(object):
    
    TYPE_NORMAL = 0
    TYPE_RATE = 1
    TYPE_DELTA = 2

    # -------------------------------------------------------------------- #
    
    GRAPH_KINDS = {}
    
    @staticmethod
    def getGraphDesc(csv_path):
        global tl_graph_count
        
        line_width = 2
        zorder = 10
        yshift = 0
        marker = None
        kind = os.path.basename(csv_path).split("-")[0].split("_")[0]
        if kind in ["timeline.csv"]:
            ymax = 1
            graph_type = Graph.TYPE_DELTA
            line_width = 3
        elif kind in ["TL"]:
            line_width = 1
            ymax = 20
            yshift = tl_graph_count * 1.1
            graph_type = Graph.TYPE_NORMAL
            zorder = 1
            tl_graph_count += 1
        elif kind in ["STIME", "UTIME"]:
            ymax = 3200
            graph_type = Graph.TYPE_RATE
        elif kind in ["RDTA", "TDTA"]:
            ymax = 150000
            graph_type = Graph.TYPE_RATE
        elif kind in ["GPU"]:
            ymax = 300
            graph_type = Graph.TYPE_NORMAL
        else:
            return None
        return GraphDesc(graph_type, ymax, yshift, line_width, marker, zorder)

    # -------------------------------------------------------------------- #
        
    def __init__(self, label, csv_path, desc, xstart = 0, ltrim = None, rtrim = None):
        self._label = label
        self._csv_path = csv_path
        self._desc = desc
        self._color = None
        self._ax = None
        self._is_visible = False
        self._xstart = xstart
        self._ltrim = ltrim
        self._rtrim = rtrim
        self._readData()
    
    # -------------------------------------------------------------------- #
        
    def _readData(self):
        self._current_section = Section(None)
        self._sections = [self._current_section]
        
        ####################
        # Read graph data: #
        ####################
        i = 0
        last_val = None
        last_timestamp = None
        with open(self._csv_path, "r") as csv:
            for line in csv:
                line = line.strip()
                parts = line.replace(" ","").split(",")
                try:
                    timestamp = float(parts[0])
                    if self._ltrim and (timestamp < self._ltrim):
                        continue
                    if self._rtrim and (timestamp > self._rtrim):
                        continue
                    timestamp -= self._xstart
                    val = float(parts[1])
                    if len(parts) >= 3:
                        label = parts[2]
                        if label != self._current_section.label:
                            self._current_section = Section(label)
                            self._sections.append(self._current_section)
                            if not label in label_colors:
                                color_id = len(label_colors) % len(COLORS)
                                label_colors[label] = COLORS[color_id]
                except:
                    print "Error in %s: %u \"%s\." % (self._csv_path, i, line)
                    continue
                i += 1
                
                if self._desc.graph_type == Graph.TYPE_NORMAL:
                    xs = [timestamp]
                    ys = [val]
                elif self._desc.graph_type == Graph.TYPE_RATE:
                    rate = 0 if last_val is None else (val - last_val) / (timestamp - last_timestamp)
                    if rate > 1000000:
                        print "Error in %s: %u \"%s\." % (self._csv_path, i, line)
                        continue
                    last_timestamp = timestamp
                    last_val = val
                    xs = [timestamp]
                    ys = [rate]
                elif self._desc.graph_type == Graph.TYPE_DELTA:
                    xs = [timestamp, timestamp, timestamp]
                    ys = [0, 1, 0]
        
                for i in range(len(ys)):
                    ys[i] += self._desc.yshift
                
                self._current_section.x.extend(xs)
                self._current_section.y.extend(ys)
        
        if len(self._sections[0].x) == 0:
            self._sections.pop(0)
        
        #for section in self._sections:
            #print "%s: %s %s" % (section.label, section.x, section.y)
    
    # -------------------------------------------------------------------- #
    
    def csvPath(self):
        return self._csv_path
    
    # -------------------------------------------------------------------- #
    
    def color(self):
        return self._color
    
    # -------------------------------------------------------------------- #
    
    def setColor(self, val):
        self._color = val
    
    # -------------------------------------------------------------------- #
        
    def isVisible(self):
        return self._is_visible
    
    # -------------------------------------------------------------------- #
    
    def min_x_val(self):
        return 0 if len(self._sections) == 0 else self._sections[0].x[0]

    # -------------------------------------------------------------------- #
    
    def max_x_val(self):
        return 0 if len(self._sections) == 0 else self._sections[-1].x[-1]
    
    # -------------------------------------------------------------------- #
    
    def isInVisibleRectX(self, host):
        host_xmin, host_xmax = host.get_xlim() # Visible rectangle
        return (self.min_x_val() < host_xmax) and (self.max_x_val() > host_xmin) 
        
    # -------------------------------------------------------------------- #
    
    def plot(self, fig, host):
        #print "PLOTTING %s" % self._csv_path
        first_time = self._ax is None
        host_ymin, host_ymax = host.get_ylim() # Visible rectangle
        if first_time:
            self._ax = host.twinx()
            #self._ax.set_ylabel(self._label, color=self._color)
            #self._ax.axes.get_yaxis().set_ticklabels([])        
            #xmin = self.min_x_val() if host_xmin == 0.0 else min(host_xmin, self.min_x_val())
            #xmax = self.max_x_val() if host_xmax == 0.0 else max(host_xmax, self.max_x_val())
            #xdelta = xmax - xmin 
            #if xmin != host_xmin:
            #    xmin -= xdelta * 0.02
            #if xmax != host_xmax:
            #    xmax += xdelta * 0.02 
            #self._ax.set_xlim(xmin, xmax)
            #print "CREATED GRAPH %s" % self._csv_path
        else:
            pass

        ymin = self._desc.ymax * host_ymin # (0-1)
        ymax = self._desc.ymax * host_ymax # (0-1)
        autoscale_x = False #first_time #(host_xmin == 0.0) and (host_xmax == 1.0) # Only if not zoomed yet
        autoscale_y = False
        self._ax.set_autoscalex_on(autoscale_x)
        self._ax.set_autoscaley_on(autoscale_y)
        
        for section in self._sections:
            if section.label is None:
                color = self._color
            else:
                color = label_colors.get(section.label, "r")
            self._ax.plot(section.x, section.y, color, linewidth = self._desc.line_width, marker = self._desc.marker, zorder = self._desc.zorder)
        
        self._ax.set_ylim(ymin, ymax)
        self._ax.tick_params('y', colors = self._color)
        self._ax.spines['top'].set_visible(True)
        self._ax.spines['right'].set_visible(True)
        self._ax.spines['bottom'].set_visible(True)
        self._ax.spines['left'].set_visible(True)
        self._ax.axes.get_yaxis().set_visible(True)
        self._ax.axes.get_xaxis().set_visible(True)
        self._ax.locator_params(nbins=10, axis='x')
        self._ax.xaxis.grid(b=True, which='minor')
        self._ax.xaxis.grid(b=True, which='major')
        self._ax.minorticks_on()
        self._is_visible = True
        return fig, host, first_time
    
    # -------------------------------------------------------------------- #
    
    def clear(self):
        #print "CLEARING %s" % self._csv_path
        self._ax.spines['top'].set_visible(False)
        self._ax.spines['right'].set_visible(False)
        self._ax.spines['bottom'].set_visible(False)
        self._ax.spines['left'].set_visible(False)
        self._ax.axes.get_yaxis().set_visible(False)
        self._ax.axes.get_xaxis().set_visible(False)
        self._ax.clear()
        self._ax.minorticks_on()
        self._is_visible = False
    
    # -------------------------------------------------------------------- #
    
    def readData(self):
        self._readData()
    
    # -------------------------------------------------------------------- #
    
    def setXStart(self, start):
        shift = start - self._xstart
        for section in self._sections:
            for i in range(len(section.x)):
                section.x[i] -= shift
        self._xstart = start
    
    # -------------------------------------------------------------------- #
    
#     def scaleTo(self, host):
#         base_ymax = self._ymax if self._ymax is not None else max(self._y)
#         base_ymin = 0
#         host_ymin, host_ymax = host.get_ylim()
#         yrange = base_ymax - base_ymin
#         ymax = yrange * host_ymax # host_ymax is between 0 and 1
#         ymin = yrange * host_ymin # host_ymax is between 0 and 1
#         print yrange
#         print (host_ymin, host_ymax)
#         print (ymin, ymax)
#         self._ax.set_ylim(ymin, ymax)
        

###############################################################################

# class GraphFileTreeWidgetItem(QTreeWidgetItem):
#     
#     def __init__(self, parent, csv_path):
#         QTreeWidgetItem.__init__(self, parent)
#         
#         self._csv_path = csv_path
#         self.widget = QWidget()
#         self.widget.setLayout(QHBoxLayout())
#         self.cb_enabled = QCheckBox()
#         self.le_label = QLineEdit("")
#         self.cb_graph_type = QComboBox()
#         self.cb_graph_type.addItems(["NORMAL", "RATE", "DELTA"])
#         
#         self.widget.layout().addWidget(self.cb_enabled)
#         self.widget.layout().addWidget(QLabel(os.path.basename(csv_path)))
#         self.widget.layout().addWidget(QLabel("Label:"))
#         self.widget.layout().addWidget(self.le_label)
#         self.widget.layout().addWidget(QLabel("Type:"))
#         self.widget.layout().addWidget(self.cb_graph_type)
#         
#         self.treeWidget().setItemWidget(self, 0, self.widget)

###############################################################################

class MLGraphViewer(QMainWindow):
        
    def __init__(self, dirs, parent=None):
        QMainWindow.__init__(self, parent)

        self._dirs = dirs
        self._graphs = {}
        self._timelines = {}
        self._handleChanges = True
        
        self.setWindowTitle('ML Graph Viewer')

        self.sb_sync_step = QSpinBox()
        self.sb_sync_step.valueChanged.connect(self._onSyncStepChanged)
    
        self.create_menu()
        self.create_main_frame()
        self.create_status_bar()

    # -------------------------------------------------------------------- #

    def _scaleXToFit(self):
        active_graphs = [graph for graph in self._graphs.values() if graph.isVisible()]
        if len(active_graphs) == 0:
            return
        
        x_min = min([graph.min_x_val() for graph in active_graphs])
        x_max = max([graph.max_x_val() for graph in active_graphs])
        if ((x_min, x_max) == (0.0, 1.0)) or (x_min >= x_max):
            return

        x_delta = x_max - x_min
        x_min -= 0.02 * x_delta
        x_max += 0.02 * x_delta
        self.host.set_xlim(x_min, x_max)
            
    # -------------------------------------------------------------------- #

    def _onXlimsChange(self, axes):
        #print "updated xlims: ", axes.get_xlim()
        #if axes.get_xlim() == (0.0, 1.0):
            # print "Reset"
            # self._resetZoom()
        pass
    
    # -------------------------------------------------------------------- #
    
    def _onYlimsChange(self, axes):
        #print "updated ylims: ", axes.get_ylim()
        pass

    # -------------------------------------------------------------------- #
    
    def _getNextColor(self):
        for c in COLORS:
            if COLOR_MAP[c]:
                return c
        raise Exception("No more available colors.")
    
    # -------------------------------------------------------------------- #
    
    def _getOrCreateTimeline(self, csv_path):
        dir_path = os.path.dirname(csv_path)
        timeline = self._timelines.get(dir_path)
        if not timeline:
            timeline = []
            timeline_path = os.path.join(dir_path, "timeline.csv")
            if os.path.isfile(timeline_path):
                with open(timeline_path) as timeline_file:
                    timeline_file.readline() # Skip 1st step
                    for line in timeline_file:
                        step_time = float(line.split(",")[0])
                        timeline.append(step_time)
        return timeline
    
    # -------------------------------------------------------------------- #
    
    def _getShift(self, csv_path):
        sync_step = self.sb_sync_step.value()
        timeline = self._getOrCreateTimeline(csv_path)
        shift = timeline[sync_step]
        return shift
    
    # -------------------------------------------------------------------- #
    
    def _getEpoch(self, csv_path):
        timeline = self._getOrCreateTimeline(csv_path)
        return timeline[0]
        
    # -------------------------------------------------------------------- #
    
    def _getOrCreateGraph(self, csv_path):
        csv_path = str(csv_path)
        if csv_path in self._graphs:
            graph = self._graphs[csv_path]
        else:
            label = csv_path #
            desc = Graph.getGraphDesc(csv_path)
            shift = self._getShift(csv_path)
            epoch = self._getEpoch(csv_path)
            graph = Graph(label, csv_path, desc, shift, ltrim=epoch)
            self._graphs[csv_path] = graph
        return graph
    
    # -------------------------------------------------------------------- #
    
    def _plotGraph(self, graph, tree_item):
        ###################
        # Allocate color: #
        ###################
        color = self._getNextColor()
        graph.setColor(color)
        COLOR_MAP[graph.color()] = False
        
        self.fig, self.host, first_time = graph.plot(self.fig, self.host)
        if (first_time and len(self._graphs) == 1) or (not graph.isInVisibleRectX(self.host)):
            self._scaleXToFit()
        tree_item.setBackground(0, QBrush(QColor(graph.color())))
        tree_item.setCheckState(0, Qt.Checked)
            
    # -------------------------------------------------------------------- #
    
    def _unplotGraph(self, graph, tree_item):
        ###############
        # Free color: #
        ###############
        if graph.color() is not None:
            COLOR_MAP[graph.color()] = True
        
        graph.clear()
        tree_item.setBackground(0, QBrush())
        tree_item.setCheckState(0, Qt.Unchecked)
        
    # -------------------------------------------------------------------- #

    def _onTreeItemChanged(self, item):
        if not self._handleChanges:
            return 
        
        csv_path = item.data(0, Qt.UserRole).toString()
        graph = self._getOrCreateGraph(csv_path)

        self._handleChanges = False
        if item.checkState(0) == Qt.Checked:
            self._plotGraph(graph, item)
            style_widget = QPushButton("...")
            self._tree.setItemWidget(item, 1, style_widget)
        else:
            self._unplotGraph(graph, item)
        self._handleChanges = True
        self.canvas.draw()
    
    # -------------------------------------------------------------------- #
    
    def _findItem(self, graph):
        csv_path = graph.csvPath()
        csv_name = os.path.basename(csv_path)
        tree_items = self._tree.findItems(csv_name, Qt.MatchRecursive)
        for item in tree_items:
            if item.data(0, Qt.UserRole) == csv_path:
                return item
        return None

    # -------------------------------------------------------------------- #
    
    def _resetHost(self):
        self.host.axis('off')
        #self.host.xaxis.set_major_locator(ticker.MultipleLocator(0.05))
        #self.host.locator_params(nbins=10, axis='x')
        #self.host.axes.get_yaxis().set_visible(False)
        #self.host.axes.get_xaxis().set_visible(True)
        #self.host.spines['top'].set_visible(False)
        #self.host.spines['right'].set_visible(False)
        #self.host.spines['bottom'].set_visible(True)
        #self.host.spines['left'].set_visible(False)
        #self.host.spines["right"].set_position(("axes", 1.0))
        self.host.set_autoscale_on(False)
    
    # -------------------------------------------------------------------- #
    
    def _repaintCanvas(self):
        self.canvas.draw()
    
    # -------------------------------------------------------------------- #
    
    def resetZoom(self):
        self.host.set_ylim(0.0, 1.0)
        for graph in self._graphs.values():
            if graph.isVisible():
                graph.plot(self.fig, self.host)
        self._scaleXToFit()
        self._repaintCanvas()
        
    # -------------------------------------------------------------------- #
    
    def _shiftAll(self):
        for graph in self._graphs.values():
            shift = self._getShift(graph.csvPath())
            graph.setXStart(shift)
            if graph.isVisible():
                graph.clear()
                graph.plot(self.fig, self.host)
        self._repaintCanvas()
        
    # -------------------------------------------------------------------- #
    
    def _refreshAll(self):
        self._handleChanges = False
        self._tree.clear()
        for dir in self._dirs:
            name = os.path.basename(os.path.normpath(dir))
            top_level_item = QTreeWidgetItem(self._tree, [name])
            top_level_item.setExpanded(True)
            self._loadDir(dir, top_level_item)
        
        global tl_graph_count
        tl_graph_count = 0
        dead_graphs = []
        for graph in self._graphs.values():
            tree_item = self._findItem(graph)
            if tree_item is None:
                dead_graphs.append(graph)
            else:
                if graph.isVisible():
                    tree_item.setBackground(0, QBrush(QColor(graph.color())))
                    tree_item.setCheckState(0, Qt.Checked)
                    while tree_item is not None:
                        tree_item.setExpanded(True)
                        tree_item = tree_item.parent()

        ######################
        # Close dead graphs: #
        ######################
        for graph in dead_graphs:
            csv_path = graph.csvPath()
            print "Warning: Graph %s no longer exists." % csv_path
            if graph.isVisible():
                graph.clear()
            del self._graphs[csv_path]

        ###################
        # Refresh graphs: #
        ###################
        for graph in self._graphs.values():
            graph.readData()
            if graph.isVisible():
                graph.clear()
                graph.plot(self.fig, self.host)
        self._repaintCanvas()
        
        self._handleChanges = True
    
    # -------------------------------------------------------------------- #
    
    def _onSyncStepChanged(self):
        self._shiftAll()
    
    # -------------------------------------------------------------------- #
    
    def _onRefreshClicked(self):
        self._refreshAll()
        
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
            
            Many thanks to Eli Bendersky for the PyPlot skeleton. 
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
        from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
        from matplotlib.figure import Figure
        
        def new_home(self, *args, **kwargs):
            self.resetZoom()
    
        NavigationToolbar.home = new_home
        
        self.main_frame = QWidget()
        
        # Create the mpl Figure and FigCanvas objects. 
        # 5x4 inches, 100 dots-per-inch
        #
        #self.dpi = 100
        self.fig = Figure() #(5.0, 4.0), dpi=self.dpi)
        #self.fig.patch.set_visible(False)
        self.host = self.fig.add_subplot(1, 1, 1)
        self._resetHost()
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setParent(self.main_frame)
        self.fig.tight_layout(pad=0)
        self.fig.subplots_adjust(left = 0.01, right = 0.92, top = 0.98, bottom = 0.09)
        
        self.host.callbacks.connect('xlim_changed', self._onXlimsChange)
        self.host.callbacks.connect('ylim_changed', self._onYlimsChange)        
        
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
        #self._tree.setColumnCount(2)

        #self._tree.setHeaderLabels(["Files", "Settings"])
        self._refreshAll()
        self._tree.itemChanged.connect(self._onTreeItemChanged)
        
        self.b_refresh = QPushButton("Refresh")
        self.b_refresh.clicked.connect(self._onRefreshClicked)
        
        file_select_pane = QWidget(splitter)
        file_select_pane.setLayout(QVBoxLayout())
        file_select_pane.layout().addWidget(self._tree)
        
        sync_pane = QHBoxLayout()
        sync_pane.addWidget(QLabel("Step:"))
        sync_pane.addWidget(self.sb_sync_step)
        
        file_select_pane.layout().addLayout(sync_pane)
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
