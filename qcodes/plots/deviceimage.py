# A device image plotter

import sys
import os
import time
import json
import PyQt5.QtWidgets as qt
import PyQt5.QtGui as gui
import PyQt5.QtCore as core

from functools import partial
from shutil import copyfile

class MakeDeviceImage(qt.QWidget):
    """
    Class for clicking and adding labels
    """

    def __init__(self, app, folder):

        super().__init__()

        self.qapp = app
        self.folder = folder

        # BACKEND
        self._data = {}
        self.filename = None

        # FRONTEND

        grid = qt.QGridLayout()
        self.setLayout(grid)

        self.imageCanvas = qt.QLabel()
        self.loadButton = qt.QPushButton('Load image')
        self.labelButton = qt.QPushButton('Insert Label')
        self.annotButton = qt.QPushButton('Place annotation')
        self.channelLabel = qt.QLabel('Channel number')
        self.channelNumber = qt.QLineEdit()
        self.okButton = qt.QPushButton('Save and close')

        self.loadButton.clicked.connect(self.loadimage)
        self.labelButton.clicked.connect(partial(self.setlabel_or_annotation,
                                                 argument='label'))
        self.annotButton.clicked.connect(partial(self.setlabel_or_annotation,
                                                 argument='annotation'))
        self.imageCanvas.mousePressEvent = None
        self.imageCanvas.setStyleSheet('background-color: red')
        self.okButton.clicked.connect(self.saveAndClose)

        grid.addWidget(self.imageCanvas, 0, 0, 4, 6)
        grid.addWidget(self.loadButton, 4, 0)
        grid.addWidget(self.labelButton, 4, 1)
        grid.addWidget(self.annotButton, 4, 2)
        grid.addWidget(self.channelLabel, 4, 3)
        grid.addWidget(self.channelNumber, 4, 4)
        grid.addWidget(self.okButton, 4, 5)

        self.resize(600, 400)
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
        self._data[number]['value'] = 'Ch. {:02d} mV'.format(int(number))

        # draw it

        self.imageCanvas, _ = self._renderImage(self._data,
                                                self.imageCanvas,
                                                self.filename)

    def saveAndClose(self):
        """
        Save and close
        """
        if self.filename is None:
            return

        fileformat = self.filename.split('.')[-1]
        rawpath = os.path.join(self.folder, 'deviceimage_raw.'+fileformat)
        copyfile(self.filename, rawpath)

        # Now forget about the original
        self.filename = rawpath

        self.close()

    def _getpos(self, event):
        self.gotclick = True
        self.click_x = event.pos().x()
        self.click_y = event.pos().y()

    @staticmethod
    def _renderImage(data, canvas, filename):
        """
        Render an image
        """

        pixmap = gui.QPixmap(filename)
        width = pixmap.width()
        height = pixmap.height()

        label_size = min(height/10, width/10)

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
                painter.drawRect(ax, ay, 2.75*label_size, label_size)
                textfont = gui.QFont('Decorative', 0.5*label_size)
                painter.setBrush(gui.QColor(50, 50, 50))
                painter.setFont(textfont)
                painter.drawText(core.QRectF(ax+2, ay+0.4*label_size,
                                             3*label_size,
                                             label_size),
                                 channel['value'])

            canvas.setPixmap(pixmap)

        return canvas, pixmap


class DeviceImage:

    """
    Manage an image of a device
    """

    def __init__(self, folder):

        self._data = {}
        self.filename = None
        self.folder = folder

    def annotateImage(self):
        """
        Launch a Qt Widget to click
        """
        app = qt.QApplication(sys.argv)
        imagedrawer = MakeDeviceImage(app, self.folder)
        app.exec_()
        self._data = imagedrawer._data
        self.filename = imagedrawer.filename
        imagedrawer.close()
        app.quit()
        self.saveAnnotations()

    def saveAnnotations(self):
        """
        Save annotated image to disk (image+instructions)
        """
        filename = os.path.join(self.folder, 'deviceimage_annotations.json')
        with open(filename, 'w') as fid:
            json.dump(self._data, fid)

    def loadAnnotations(self):
        """
        Get the annotations. Only call this if the files exist
        """
        filename = os.path.join(self.folder, 'deviceimage_annotations.json')
        with open(filename, 'r') as fid:
            self._data = json.load(fid)

    def updateValues(self, qdac):
        """
        Update the data with actual voltages from the QDac
        """
        for channum in self._data.keys():
            param = qdac.parameters['ch{:02d}_v'.format(int(channum))]
            voltage = param.get_latest()
            fmtstr = '{:0.1f} mV'
            self._data[channum]['value'] = fmtstr.format(1e3*voltage)

    def makePNG(self, counter):
        """
        Render the image with new voltage values and save it to disk

        Args:
            counter (int): A counter for the experimental run number
        """
        if self.filename is None:
            raise ValueError('No image selected!')

        app = qt.QApplication(sys.argv)

        win = qt.QWidget()
        grid = qt.QGridLayout()
        win.setLayout(grid)
        win.imageCanvas = qt.QLabel()
        grid.addWidget(win.imageCanvas)

        win.imageCanvas, pixmap = MakeDeviceImage._renderImage(self._data,
                                                               win.imageCanvas,
                                                               self.filename)

        filename = 'deviceimage_{:03d}.png'.format(counter)
        pixmap.save(filename, 'png')
        app.quit()
