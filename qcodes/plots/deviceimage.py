# A device image plotter

import sys
import os
import PyQt5.QtWidgets as qt
import PyQt5.QtGui as gui



class MakeDeviceImage(qt.QWidget):
    """
    Class for clicking and adding labels
    """

    def __init__(self):

        super().__init__()

        grid = qt.QGridLayout()
        self.setLayout(grid)

        self.imageCanvas = qt.QLabel()
        # gui.QPixmap
        # self.imagelabel.setPixmap(...)
        ###self.imageCanvas.setPixmap('/Users/william/Downloads/device800.jpeg')

        self.loadButton = qt.QPushButton('Load image')
        self.labelButton = qt.QPushButton('Insert Label')
        self.annotButton = qt.QPushButton('Place annotation')

        self.loadButton.clicked.connect(self.loadimage)

        grid.addWidget(self.imageCanvas, 0, 0, 4, 4)
        grid.addWidget(self.loadButton, 4, 0)
        grid.addWidget(self.labelButton, 4, 1)

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
        self.imageCanvas.setPixmap(pixmap)

    def setlabel(self):
        """
        Set the position for a channel label.
        """
        number = 10  # TODO: the user should input this


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
    _ = MakeDeviceImage()
    sys.exit(app.exec_())
