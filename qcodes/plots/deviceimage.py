# A device image plotter

import sys
import os
import time
import PyQt5.QtWidgets as qt
import PyQt5.QtGui as gui

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
        self.channelNumber = qt.QLineEdit

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
        pixmap = gui.QPixmap(filename[0])
        width = pixmap.width()
        height = pixmap.height()

        self.imageCanvas.setPixmap(pixmap)

        print(self.imageCanvas.frameSize())

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

        number = self.channelLabel.getText()

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

    def _getpos(self, event):
        self.gotclick = True
        self.click_x = event.pos().x()
        self.click_y = event.pos().y()

    def _drawitall(self):
        """
        Draws stuff... probably reusable.
        """
        pass

class DeviceImage:

    """
    Manage an image of a device
    """

    def __init__(self):

        pass

    def makeImage(self):
        """
        Launch a Qt Widget to click
        """
        pass


def testgui():

    app = qt.QApplication(sys.argv)
    _ = MakeDeviceImage(app)
    sys.exit(app.exec_())
