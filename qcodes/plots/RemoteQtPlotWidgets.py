
import sys
import numpy as np

from colors import color_cycle, colorscales, colorscales_raw
# import qcodes.plots.colors.colorscales as colorscales

import pyqtgraph as pg






def make_rgba(colorscale):
    dd = {}
    dd['ticks'] = [(v, one_rgba(c)) for v, c in colorscale]
    dd['mode'] = 'rgb'
    return dd


def one_rgba(c):
    '''
    convert a single color value to (r, g, b, a)
    input can be an rgb string 'rgb(r,g,b)', '#rrggbb'
    if we decide we want more we can make more, but for now this is just
    to convert plotly colorscales to pyqtgraph tuples
    '''
    if c[0] == '#' and len(c) == 7:
        return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), 255)
    if c[:4] == 'rgb(':
        return tuple(map(int, c[4:-1].split(','))) + (255,)
    raise ValueError('one_rgba only supports rgb(r,g,b) and #rrggbb colors')


__colorscales = {}

for scale_name, scale in colorscales_raw.items():
    __colorscales[scale_name] = make_rgba(scale)

__colorscales['grey'] = __colorscales.pop('Greys') #pg.graphicsItems.GradientEditorItem.Gradients['grey']
cc = pg.pgcollections.OrderedDict(__colorscales)


pg.graphicsItems.GradientEditorItem.Gradients = cc

from pyqtgraph import dockarea


from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget, QShortcut, QHBoxLayout
from PyQt5.QtCore import QBuffer, QIODevice, QByteArray
from PyQt5.QtCore import QObject, pyqtSlot


qtapp = QtGui.QApplication([])



class PlotTrace(pg.PlotDataItem):

    '''
    PlotDataItem with benefits

    delete()
    update()
    - check if data has been updated
    - call set_data() with the updated data



    '''


    def setData(self, *args, **kwargs):

        y = None
        x = None
        if len(args) == 1:
            kwargs['y'] = args[0]

        elif len(args) == 2:
            kwargs['x'] = args[0]
            kwargs['y'] = args[1]

        maskx = False
        masky = False
        if 'x' in kwargs:
            x = kwargs['x']
            maskx = np.isfinite(x)
        if 'y' in kwargs:
            y = kwargs['y']
            masky = np.isfinite(y)

        if ('x' in kwargs) and ('y' in kwargs):
            if np.shape(maskx) == np.shape(masky):
                maskx = maskx & masky
                masky = maskx
        if 'x' in kwargs:
            kwargs['x'] = kwargs['x'][maskx]

        if 'y' in kwargs:
            kwargs['y'] = kwargs['y'][masky]

        self.x = x
        self.y = y
        super().setData(**kwargs)

    def update_data(self):
        # self.updateItems()
        if self.y is not None:
            if self.x is not None:
                maskx, masky = np.isfinite(self.x), np.isfinite(self.y)
                if np.shape(maskx) == np.shape(masky):
                    maskx = maskx & masky
                    masky = maskx

                super().setData(self.x[maskx], self.y[masky])
            else:
                masky = np.isfinite(self.y)
                super().setData(self.y[masky])
        # else:
        #     print('fail')


class PlotImage(pg.ImageItem):

    '''
    ImageItem with benefits

    delete()
    update()
    - check if data has been updated
    - call set_data() with the updated data
    '''

    # def __init__(self, *args, **kwargs)
    def __init__(self, *args, **kwargs):
        self._hist_range = (np.nan, np.nan)
        super().__init__(*args, **kwargs)

    # def regionChanging(self, *args, **kwargs):
    #     self.auto_range = False
    #     pass
    #     # print('regionChanging', args, kwargs)


    # def regionChanged(self, *args, **kwargs):
    #     pass
    #     # print('regionChanged', args, kwargs)

    def setImage(self, *args, **kwargs):
        # self._hist.region.sigRegionChanged.connect(self.regionChanging)
        # self._hist.region.sigRegionChangeFinished.connect(self.regionChanged)
        x = kwargs.get('x', None)
        y = kwargs.get('y', None)
        z = kwargs.get('z', None)

        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if z is not None:
            self.z = z


        # self.setOpts(axisOrder='row-major')
        # self.transpose = kwargs.get('transpose', False)
        # TODO transpose does not work yet :O
        self.transpose = False

        # self.auto_range = True
        super().setImage(*args, **kwargs)

        if any([x is not None,y is not None,z is not None]):
            self.update_data()

        # self.update_data()
        # if self.image is not None:
        #     self.z_range = (np.nanmin(self.image), np.nanmax(self.image))
        # else:
        #     self.z_range = (0, 1)


    #     print(args)
    #     print('argsargsargsargsargsargsargsargsargsargsargs')
    #     print(kwargs)
    #     self.y = None
    #     self.x = None
    #     self.z = None

    #     if len(args) == 3:
    #         self.x = args[0]
    #         self.y = args[1]
    #         self.z = args[2]

    #     # else:
    #     #     raise('error zzz')
    #     self.z = kwargs.get('z', None)

    #     if len(args) == 1:
    #         self.z = args[0]


    #     print('ooooo')
    #     print(self.z)

    # def setLevels(self, *args, **kwargs):
        # print('setLevels')
        # print(args)
        # print(kwargs)
        # self.auto_range = False
        # super().setLevels(*args, **kwargs)

    def update_data(self):
        # print('x update')

        if self.image is None:
            return

        hist_range = (np.nanmin(self.image), np.nanmax(self.image))

        if (self._hist.getLevels() == self._hist_range) or np.isnan(self._hist_range).any():
            self._hist_range = hist_range
            self._hist.setLevels(*self._hist_range)

        # old_range = self._hist.getLevels()

        # return
        # if h[0] is not None:
        #     # return
        # # if autoLevel:
        #     mn = h[0][0]
        #     mx = h[0][-1]

            # self._hist.region.setRegion([mn, mx])

        # if self.z_range == hist_range:
        #     self.z_range = z_range
        #     # self._hist..region.setRegion()
        #     self.setLevels(z_range, update=True)
            # self._hist.setLevels(*z_range)
            # self.levels = self._hist.getLevels()
            # print(self._hist.getLevels())



        # h = self.getHistogram()
        # hi = tuple([h[0][0], h[0][-1]])
        # print(self.z_range == hi)
        # print(self.z_range, hi)

        # self.z_range = hi
        # print('xxx')

        # return

        # if self.image is None:
        #     print('NONE')
        #     # super().setImage(self.image)
        #     return

        finite = np.isfinite(self.z)

        if not np.any(finite):
            return

        f0, f1 = np.any(finite, axis=0), np.any(finite, axis=1)

        min0, min1 = np.argmax(f0),np.argmax(f1)

        max0, max1 = len(f0) - np.argmax(f0[::-1]), len(f1) - np.argmax(f1[::-1])

        mask1 = slice(min1, max1)
        mask0 = slice(min0, max0)

        # if self.transpose:
        #     # self.x, self.y = self.y, self.x
        #     super().setImage(self.image[minX:maxX+1,minY:maxY+1][::-1,::].T, levels=z_range)
        #     # print('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXxx')
        #     finite = finite.T
        # else:
        # super().setImage()

        self.image = self.z[mask1, mask0]
        self.updateImage()
        self.sigImageChanged.emit()  # updateimage does not know about the new data

        # return

        if (self.x is not None) and (self.y is not None):

                x0 = np.nanmin([np.nanmax(self.x[mask1]), np.nanmin(self.x[mask1])])
                width = np.nanmax(self.x[mask1]) - np.nanmin(self.x[mask1])
                if width == 0:
                    width = 1
                dx = width / (mask1.stop - mask1.start)

                y0 = np.nanmin([np.nanmax(self.y[mask0]), np.nanmin(self.y[mask0])])
                height = np.nanmax(self.y[mask0]) - np.nanmin(self.y[mask0])
                if height == 0:
                    height = 1
                dy = height / (mask0.stop - mask0.start)



                px, py, sx, sy = x0-dx/2, y0-dy/2, width, height#+dy/2

                if width == 1:
                    sx = 1
                if height == 1:
                    sy = 1
            # print(np.nanmax(self.x), np.nanmin(self.x))
            # print(x0-dx/2, y0+dy/2, width+dx, -(height+dy))
        else:
            return

        # if np.isnan([]).any():
            # return

        # if sx == 0 or sy == 0:
            # return

        print('XXXXXXX')
        print(mask1.stop - mask1.start)
        print(mask0.stop - mask0.start)
        print(x0, y0, width, height, dx, dy)
        print(px, py, sx, sy)

        # if px == np.nan:
        #     px = mask0.start

        # if py == np.nan:
        #     py = mask1.start

        # if (sx == np.nan) or (sx == 0):
        #     if self.transpose:
        #         sx = mask1.stop
        #     else:
        #         sx = mask0.stop

        # if (sy == np.nan) or (sy == 0):
        #     if self.transpose:
        #         sy = mask0.stop
        #     else:
        #         sy = mask1.stop


        # print('YYYYYY')
        # print(x0, y0, width, height, dx, dy)
        # print(px, py, sx, sy)
        # sy = mask1.stop

        # print((px, py, sx, sy))
        # rect = QtCore.QRectF(minX, maxY, max(maxX, 1), max(maxY, 1))

        # print(minX, maxX)
        # print(minY, maxY)

        # return
        rect = QtCore.QRectF(px, py, sx, sy)  # topleft point and widths
        self.setRect(rect)

    # def updateImage(self, *args, **kwargs):
    #     print(args)
    #     print(kwargs)
    #     if self.image is not None:
    #         super().updateImage(*args, **kwargs)




class PlotDock(dockarea.Dock):
    '''
    Dock with benefits

    - contains a list of traces

    - turns on and of Hist item

    setGeometry()
    clear()
    save()
    to_matplolib()
    '''
    def __init__(self, *args, **kwargs):
        self.theme = ((60, 60, 60), 'w')
        self.grid = 20
        # self.theme = ((0, 0, 0), 'w')
        if 'theme' in kwargs.keys():
            self.theme = kwargs.pop('theme')

        super().__init__(*args, **kwargs)

        self.dock_widget = pg.GraphicsLayoutWidget()
        self.dock_widget.setBackground(self.theme[1])

        self.hist_item = pg.HistogramLUTWidget()
        self.hist_item.item.vb.setMinimumWidth(10)
        self.hist_item.setMinimumWidth(120)
        self.hist_item.setBackground(self.theme[1])
        self.hist_item.axis.setPen(self.theme[0])
        self.hist_item.hide()

        cmap = getattr(kwargs, 'cmap', 'viridis')
        self.set_cmap(cmap)

        # self.hist_item.setLevels()

        self.addWidget(self.dock_widget, 0, 0)
        self.addWidget(self.hist_item, 0, 1)

        self.plot_item = self.dock_widget.addPlot()
        self.legend = self.plot_item.addLegend(offset=(-30,30))
        self.legend.hide()


        for pos, ax in self.plot_item.axes.items():
            self.plot_item.showAxis(pos, True)

            if pos in ['top', 'right']:
                ax['item'].setStyle(showValues=False)

            ax['item'].setPen(self.theme[0])
            ax['item'].setGrid(self.grid)

        for _, ax in self.plot_item.axes.items():
            ax['item'].setPen(self.theme[0])

        def updateStyle():
            r = '2px'
            if self.label.dim:
                # This is the background-tab
                fg = '#888'
                bg = '#ddd'
                border = '#ccc'
                border_px = '1px'
            else:
                fg = '#333'
                bg = '#ccc'
                border = '#888'
                border_px = '1px'

            if self.label.orientation == 'vertical':
                self.label.vStyle = """DockLabel {
                    background-color : %s;
                    color : %s;
                    border-top-right-radius: 0px;
                    border-top-left-radius: %s;
                    border-bottom-right-radius: 0px;
                    border-bottom-left-radius: %s;
                    border-width: 0px;
                    border-right: %s solid %s;
                    padding-top: 3px;
                    padding-bottom: 3px;
                }""" % (bg, fg, r, r, border_px, border)
                self.label.setStyleSheet(self.label.vStyle)
            else:
                self.label.hStyle = """DockLabel {
                    background-color : %s;
                    color : %s;
                    border-top-right-radius: %s;
                    border-top-left-radius: %s;
                    border-bottom-right-radius: 0px;
                    border-bottom-left-radius: 0px;
                    border-width: 0px;
                    border-bottom: %s solid %s;
                    padding-left: 3px;
                    padding-right: 3px;
                }""" % (bg, fg, r, r, border_px, border)
                self.label.setStyleSheet(self.label.hStyle)
        self.label.updateStyle = updateStyle
        self.label.closeButton.setStyleSheet('border: none')


    def set_cmap(self, cmap=None, traces=None):
        if cmap is not None:
            gradient = self.hist_item.gradient
            gradient.setColorMap(self._get_cmap(cmap))


    def _get_cmap(self, scale):
        if isinstance(scale, str):
            if scale in colorscales:
                values, colors = zip(*colorscales[scale])
            else:
                raise ValueError(scale + ' not found in colorscales')
        elif len(scale) == 2:
            values, colors = scale

        return pg.ColorMap(values, colors)

    def add_item(self, *args, color=None, width=None, **kwargs):
        """
        Shortcut to .plot_item.addItem() which also figures out 1D or 2D etc.
        """
        if ('name' in kwargs) and ('z' not in kwargs):
            self.legend.show()

        if ('z' in kwargs):
            # TODO  or len(args)>2
            item = PlotImage()
            item._hist = self.hist_item
            item.setImage(kwargs['z'], **kwargs)
            self.hist_item.setImageItem(item)
            self.hist_item.show()

        else:
            if 'pen' not in kwargs:
                if color is None:
                    cycle = color_cycle
                    color = cycle[len(self.plot_item.listDataItems()) % len(cycle)]
                if width is None:
                    width = 1.5
                kwargs['pen'] = pg.mkPen(color, width=width)

            # If a marker symbol is desired use the same color as the line
            if any([('symbol' in key) for key in kwargs]):
                if 'symbolPen' not in kwargs:
                    symbol_pen_width = 1.0
                    kwargs['symbolPen'] = pg.mkPen('444', width=symbol_pen_width)
                if 'symbolBrush' not in kwargs:
                    kwargs['symbolBrush'] = color

            item = PlotTrace(*args, **kwargs)

        self.plot_item.addItem(item)

        config = {}
        for ax in ['x', 'y', 'z']:
            info = kwargs.get(ax+'_info', None)
            if info is not None:
                config[ax+'label'] = info['label']
                config[ax+'unit'] = info['unit']

        # print(config)
        if config != {}:
            self.set_labels(config)

        return item

    def set_labels(self, config=None):
        if config is None:
            config = {}

        for axletter, side in (('x', 'bottom'), ('y', 'left')):
            ax = self.plot_item.getAxis(side)
            ax.showLabel(False)
            # pyqtgraph doesn't seem able to get labels, only set
            # so we'll store it in the axis object and hope the user
            # doesn't set it separately before adding all traces
            label = config.get(axletter + 'label', None)
            unit = config.get(axletter + 'unit', None)
            ax.setLabel(label, unit)
        zlabel = config.get('zlabel', None)
        zunit = config.get('zunit', None)
        self.hist_item.axis.showLabel(False)
        self.hist_item.axis.setLabel(zlabel, zunit)

    def close(self):
        self.clear()
        super().close()

    def clear(self):
        self.plot_item.clear()
        self.set_labels()

        for sample, label in self.legend.items:
            self.legend.removeItem(label.text)
        self.legend.hide()



class QtPlot(QWidget):

    def __init__(self, *args, title=None,
                 figsize=(1000, 600), figposition=None,
                 window_title=None, theme=((60, 60, 60), 'w'),
                 parent=None, cmap='viridis', **kwargs):

        QWidget.__init__(self, parent=parent)

        # TODO update data with timing, not at every new datapoint
        self.auto_updating = False
        self.theme = theme
        self._cmap = cmap


        # if title:
        self.setWindowTitle(title or 'QtPlot')

        if figposition:
            geometry_settings = itertools.chain(figposition, figsize)
            self.setGeometry(*geometry_settings)
        else:
            self.resize(*figsize)

        self.area = dockarea.DockArea()
        # self.setStyleSheet("background-color:w;")
        p = self.palette()
        # p.setColor(self.backgroundRole(), QtGui.QColor('white'))
        p.setColor(self.backgroundRole(), QtCore.Qt.white)
        self.setPalette(p)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.area)
        self.setLayout(layout)

        self.add_dock()

        QtWidgets.QApplication.processEvents()


    def clear(self):
        self.area.clear()

        self.add_dock()

    def closeEvent(self, event):
        """
        Make sure all dock-widgets are deleted upon closing or during garbage-
        collection. Otherwise references keep plots alive forever.
        """
        self.area.deleteLater()
        self.deleteLater()
        event.accept()



    def add_dock(self, title=None, position='right',
                    relativeto=None):
        """
        Add a new dock to the current window.

        Args:
            title (str):
                Title of the dock

            position (str):
                'bottom', 'top', 'left', 'right', 'above', or 'below'

            relativeto (DockWidget, int):
                If relativeto is None, then the new Dock is added to fill an
                entire edge of the window. If relativeto is another Dock, then
                the new Dock is placed adjacent to it (or in a tabbed
                configuration for 'above' and 'below').
        """

        title = self._subplot_title(len(self._get_docks())+1, title)
        print('add dock ', title)
        subplot_dock = PlotDock(name=title, autoOrientation=False, closable=True)
        # self.set_subplot_title(subplot_dock, title)

        if type(relativeto) is int:
            print(self._get_docks())
            relativeto = self._get_docks()[relativeto - 1]
            print(relativeto)

        self.area.addDock(subplot_dock, position, relativeto)

        return subplot_dock

    def _subplot_title(self, num, title=None):
        title = '#{} - {}'.format(num, title or 'Plot')
        return title

    def _get_docks(self):
        return sorted(list(self.area.findAll()[1].keys()))

    def _get_dock(self, num, **kwargs):

        docks = self._get_docks()
        title = kwargs.get('title', None)
        position = kwargs.pop('position', 'right')
        relativeto = kwargs.pop('relativeto', None)

        print(num, len(docks))
        if num >= len(docks):
            # TODO this is not fully bug free, somehow sometimes it doeos not udate :(
            # Maybe some processEvents?
            for i in range(num - len(docks)):
                dock_args = {}
                if i == num - len(docks) - 1:
                    if position is not None:
                        dock_args['position'] = position
                    if relativeto is not None:
                        dock_args['relativeto'] = relativeto

                dock = self.add_dock(**dock_args)
        else:
            if relativeto is not None:
                print('TODO we should move the dock here now...')

        docks = self._get_docks()
        dock_indices = [int(i.split(' - ')[0][1:]) for i in docks]
        print(docks, num)



        if num <= 0:
            num = sorted(dock_indices)[num]
        #     dockindex = dock_indices.index(num)
        # else:
        dockindex = dock_indices.index(num)

        if title:
            title = self._subplot_title(num, title)
            self.area.docks[docks[dockindex]].setTitle(title)

        self.area.docks[docks[dockindex]].set_cmap(self._cmap)

        return self.area.docks[docks[dockindex]]

    def add(self, *args, subplot=1, **kwargs):
        dock = self._get_dock(subplot, **kwargs)

        # TODO add stuff from _draw_plot here
        item = dock.add_item(*args, **kwargs)

        return item




if __name__ == '__main__':

    plot = QtPlot()
    plot.show()

    dd = np.empty(100)
    dd[:] = np.nan
    pi = plot.add(dd, name='test', subplot=-1, title='JUNK', position='bottom',
                  config={'xlabel': 'xlab', 'ylabel': 'ylab', 'xunit': 'Vx', 'yunit': 'Vy'})
    # for nm, sp in plot.subplots.items():

    #     print(nm, sp)
    #     print(sp.plot_item)
    #     print(sp.plot_item.items)
    #     print(sp.plot_item.listDataItems())
    #     print()
    #     sp.clear()
    # plot.clear()
    pi3 = plot.add(dd, name='testA', subplot=-2, title='JUNK', position='bottom',
                  config={'xlabel': 'xlab', 'ylabel': 'ylab', 'xunit': 'Vx', 'yunit': 'Vy'})
    pi2 = plot.add(name='testB', subplot=2, title='JUNK2',
                   config={'xlabel': 'xlab', 'ylabel': 'ylab', 'xunit': 'Vx', 'yunit': 'Vy'})
    pi3 = plot.add(name='testC', subplot=3, title='JUNK2',
                   config={'xlabel': 'xlab', 'ylabel': 'ylab', 'xunit': 'Vx', 'yunit': 'Vy'})
    pi4 = plot.add(name='testD', subplot=4, title='JUNK2',
                   config={'xlabel': 'xlab', 'ylabel': 'ylab', 'xunit': 'Vx', 'yunit': 'Vy'})
    pi5 = plot.add(name='testE', subplot=5, title='JUNK2',
                   config={'xlabel': 'xlab', 'ylabel': 'ylab', 'xunit': 'Vx', 'yunit': 'Vy'})
    pi2 = plot.add(name='testB', subplot=-2, title='JUNK2',
                   config={'xlabel': 'xlab', 'ylabel': 'ylab', 'xunit': 'Vx', 'yunit': 'Vy'})
    pi3 = plot.add(name='testC', subplot=3, title='JUNK2',
                   config={'xlabel': 'xlab', 'ylabel': 'ylab', 'xunit': 'Vx', 'yunit': 'Vy'})



    dd[:5] = np.random.random(5)
    pi.update_data()
    pi2.update_data()


    # plot.clear()


    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
