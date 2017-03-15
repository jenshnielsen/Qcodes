# A device image plotter

import sys
import os
import time
import PyQt5.QtWidgets as qt
import PyQt5.QtGui as gui
import PyQt5.QtCore as core

from functools import partial


class MakeDeviceImage(qt.QWidget):
    """
    Class for clicking and adding labels
    """

    def __init__(self, app):

        super().__init__()

        self.qapp = app

        # BACKEND
        self._data = {}

        # FRONTEND

        grid = qt.QGridLayout()
        self.setLayout(grid)

        self.imageCanvas = qt.QLabel()
        self.loadButton = qt.QPushButton('Load image')
        self.labelButton = qt.QPushButton('Insert Label')
        self.annotButton = qt.QPushButton('Place annotation')
        self.channelLabel = qt.QLabel('Channel number')
        self.channelNumber = qt.QLineEdit()

        self.loadButton.clicked.connect(self.loadimage)
        self.labelButton.clicked.connect(partial(self.setlabel_or_annotation,
                                                 argument='label'))
        self.annotButton.clicked.connect(partial(self.setlabel_or_annotation,
                                                 argument='annotation'))
        self.imageCanvas.mousePressEvent = None
        self.imageCanvas.setStyleSheet('background-color: red')

        grid.addWidget(self.imageCanvas, 0, 0, 4, 5)
        grid.addWidget(self.loadButton, 4, 0)
        grid.addWidget(self.labelButton, 4, 1)
        grid.addWidget(self.annotButton, 4, 2)
        grid.addWidget(self.channelLabel, 4, 3)
        grid.addWidget(self.channelNumber, 4, 4)

        self.resize(500, 500)
        self.move(100, 100)
        self.setWindowTitle('Generate annotated device image')
        self.show()

    def loadimage(self):
        """
        Select an image from disk.
        """
        fd = qt.QFileDialog()
        filename = fd.getOpenFileName(self, 'Select device image',
                                      os.getcwd(),
                                      "Image files(*.jpg *png *.jpeg)")
        self.filename = filename[0]
        self.pixmap = gui.QPixmap(filename[0])
        width = self.pixmap.width()
        height = self.pixmap.height()

        self.imageCanvas.setPixmap(self.pixmap)

        # fix the image scale, so that the pixel values of the mouse are
        # unambiguous
        self.imageCanvas.setMaximumWidth(width)
        self.imageCanvas.setMaximumHeight(height)

        self.label_size = min(height/10, width/10)

    def setlabel_or_annotation(self, argument):
        """
        Set the position for a channel label or annotation
        """

        if argument not in ['label', 'annotation']:
            raise ValueError('Only labels and annotations may be saved!')

        number = self.channelNumber.text()

        self.imageCanvas.mousePressEvent = self._getpos
        self.gotclick = False
        while not self.gotclick:
            self.qapp.processEvents()
            time.sleep(0.01)  # Note: too high of a value makes clicking hard
        self.imageCanvas.mousePressEvent = None

        # update the data
        if number not in self._data.keys():
            self._data[number] = {}
        self._data[number][argument] = (self.click_x, self.click_y)

        # draw it
        #self._drawitall()
        self.imageCanvas, _ = self._renderImage(self._data,
                                                self.imageCanvas,
                                                self.filename,
                                                self.label_size)

    def _getpos(self, event):
        self.gotclick = True
        self.click_x = event.pos().x()
        self.click_y = event.pos().y()

    def _drawitall(self):
        """
        Draws stuff... probably reusable.

        """
        self.pixmap = gui.QPixmap(self.filename)

        painter = gui.QPainter(self.pixmap)
        for channum, channel in self._data.items():
            if 'label' in channel.keys():
                (lx, ly) = channel['label']
                chanstr = '{:02}'.format(int(channum))

                painter.setBrush(gui.QColor(255, 255, 255, 100))

                spacing = int(self.label_size*0.1)
                textfont = gui.QFont('Decorative', self.label_size)
                textwidth = gui.QFontMetrics(textfont).width(chanstr)

                painter.drawRect(lx-spacing, ly-spacing,
                                 textwidth+2*spacing,
                                 self.label_size+2*spacing)
                painter.setBrush(gui.QColor(25, 25, 25))

                painter.setFont(textfont)
                painter.drawText(core.QRectF(lx, ly, textwidth,
                                             self.label_size),
                                 chanstr)

            if 'annotation' in channel.keys():
                (ax, ay) = channel['annotation']
                painter.setBrush(gui.QColor(255, 255, 255, 100))
                painter.drawRect(ax, ay, 2*self.label_size, self.label_size)
                textfont = gui.QFont('Decorative', 0.25*self.label_size)
                painter.setBrush(gui.QColor(50, 50, 50))
                painter.setFont(textfont)
                painter.drawText(core.QRectF(ax+2, ay+0.4*self.label_size,
                                             2*self.label_size,
                                             self.label_size),
                                 'Chan. {} Voltage'.format(chanstr))

        self.imageCanvas.setPixmap(self.pixmap)

    @staticmethod
    def _renderImage(data, canvas, filename, label_size):
        """
        Render an image
        """

        pixmap = gui.QPixmap(filename)

        painter = gui.QPainter(pixmap)
        for channum, channel in data.items():
            chanstr = '{:02}'.format(int(channum))

            if 'label' in channel.keys():
                (lx, ly) = channel['label']

                painter.setBrush(gui.QColor(255, 255, 255, 100))

                spacing = int(label_size*0.1)
                textfont = gui.QFont('Decorative', label_size)
                textwidth = gui.QFontMetrics(textfont).width(chanstr)

                painter.drawRect(lx-spacing, ly-spacing,
                                 textwidth+2*spacing,
                                 label_size+2*spacing)
                painter.setBrush(gui.QColor(25, 25, 25))

                painter.setFont(textfont)
                painter.drawText(core.QRectF(lx, ly, textwidth,
                                             label_size),
                                 chanstr)

            if 'annotation' in channel.keys():
                (ax, ay) = channel['annotation']
                painter.setBrush(gui.QColor(255, 255, 255, 100))
                painter.drawRect(ax, ay, 2*label_size, label_size)
                textfont = gui.QFont('Decorative', 0.25*label_size)
                painter.setBrush(gui.QColor(50, 50, 50))
                painter.setFont(textfont)
                painter.drawText(core.QRectF(ax+2, ay+0.4*label_size,
                                             2*label_size,
                                             label_size),
                                 'Chan. {} Voltage'.format(chanstr))

            canvas.setPixmap(pixmap)

        return canvas, pixmap


class DeviceImage:

    """
    Manage an image of a device
    """

    def __init__(self):

        self._data = {}
        self.filename = None

    def makeImage(self):
        """
        Launch a Qt Widget to click
        """
        app = qt.QApplication(sys.argv)
        imagedrawer = MakeDeviceImage(app)
        app.exec_()
        self._data = imagedrawer._data
        self.filename = imagedrawer.filename

    def update(self, qdac):
        """
        Update the data with actual voltages from the QDac
        """
        pass

    def plot(self):
        """
        Plot the image with new voltage values.
        Can we reuse a method from MakeDeviceImage?
        """
        pass
