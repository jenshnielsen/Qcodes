# A device image plotter

import sys
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

        self.loadButton = qt.QPushButton('Load image')
        self.labelButton = qt.QPushButton('Insert Label')
        self.annotButton = qt.QPushButton('Place annotation')

        grid.addWidget(self.imageCanvas, 0, 0, 4, 4)
        grid.addWidget(self.loadButton, 4, 0)
        grid.addWidget(self.labelButton, 4, 1)

        self.resize(500, 500)
        self.move(100, 100)
        self.setWindowTitle('Generate annotated device image')
        self.show()


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
    MakeDeviceImage()
    sys.exit(app.exec_())
