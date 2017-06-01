import sys
import os
import zmq
import numpy as np
import json
import time

from pyqtgraph import dockarea

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget, QShortcut, QHBoxLayout
from PyQt5.QtCore import QBuffer, QIODevice, QByteArray
from PyQt5.QtCore import QObject, pyqtSlot

from RemoteQtPlotWidgets import QtPlot

qtapp = QtGui.QApplication([])


class DataSet():

    def __init__(self, dataset_id):
        self.id = dataset_id
        self.arrays = {}
        self.metadata = {}

    def add_metadata(self, metadata):
        self.metadata.update(metadata)

    def get_array(self, array_id, shape=100):
        if not array_id in self.arrays.keys():
            array = self.new_array(array_id, shape=shape)
        return self.arrays[array_id]

    def new_array(self, array_id, shape):
        self.arrays[array_id] = np.empty(shape=shape)
        self.arrays[array_id][:] = np.nan
        return self.arrays[array_id]

    def store(self, array_id, indices, values):
        try:
            self.arrays[array_id][indices] = values
        except:
            pass


class ZeroMQ_Listener(QtCore.QObject):

    message = QtCore.pyqtSignal(str, str, dict)

    def __init__(self, topic, port):

        QtCore.QObject.__init__(self)

        # Socket to talk to server
        context = zmq.Context()
        self.socket = context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:%s" % (port))
        self.socket.setsockopt(zmq.SUBSCRIBE, bytes(topic.encode('utf-8')))

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

        self.running = True

    def loop(self):
        while self.running:
            socks = dict(self.poller.poll(500))
            if socks.get(self.socket) == zmq.POLLIN:
                # try:
                parts = self.socket.recv_multipart()
                # print(parts)
                topic, uuid, msg = parts[:3]

                topic = topic.decode()
                uuid = uuid.decode()
                data = json.loads(msg.decode())

                if len(parts) > 3:
                    meta = parts[3]
                    meta = json.loads(meta.decode())
                    arrays = parts[4:]

                    data_arrays = {}
                    for m, a in zip(meta, arrays):
                        arr = np.frombuffer(
                            a, dtype=m['dtype']).reshape(m['shape'])

                        data_arrays[m['array_id']] = arr
                    data['add_plot']['data_arrays'] = data_arrays

                self.message.emit(topic, uuid, data)


class QtPlotWindow(QtWidgets.QWidget):

    def __init__(self, topic, port, control_port=None, parent=None, theme=((60, 60, 60), 'w'),):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.control_port = control_port

        self.stores = {}
        self.plots = []

        self.theme = theme



        self.set_title('Plot')
        self.title_parts = []

        self.plot = QtPlot()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)
        self.setLayout(layout)

        QShortcut(QtGui.QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QtGui.QKeySequence("Ctrl+Q"), self, self.close)

        desktop = QtWidgets.QApplication.desktop()
        screenRect = desktop.screenGeometry(0)
        windowRect = QtCore.QRect(0, 0, 1200, 900)
        windowRect.moveTopRight(screenRect.topRight()-QtCore.QPoint(0, -50))
        self.setGeometry(windowRect)

        self.thread = QtCore.QThread()
        self.zeromq_listener = ZeroMQ_Listener(topic, port)
        self.zeromq_listener.moveToThread(self.thread)

        self.thread.started.connect(self.zeromq_listener.loop)
        self.zeromq_listener.message.connect(self.signal_received)

        QtCore.QTimer.singleShot(0, self.thread.start)


        if self.control_port is not None:
            self.control_context = zmq.Context()
            self.control_socket = self.control_context.socket(zmq.PUB)
            self.control_socket.connect(
                "tcp://localhost:%s" % (self.control_port))

        self.control_send({'client_ready': True})
        cwd = os.getcwd()
        self.control_send({'client_dir': str(cwd)})


        # Only way on windows to make it open on top of others...
        # And it doesn't really work :O
        self.setWindowFlags(self.windowFlags() &
                            QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowFlags(self.windowFlags() & ~
                            QtCore.Qt.WindowStaysOnTopHint)
        self.show()

        self.update_interval = 1
        self._last_update = time.perf_counter()
        self._do_update = False

        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.auto_update)
        self.update_timer.start(50)

    def auto_update(self):

        # if dt < self.update_interval:
        #     QtCore.QTimer.singleShot(0.1, self._auto_update)

        if self._do_update:
            for plot in self.plots:
                # TODO only update when there is new data
                plot['plot_item'].update_data()

                self._last_update = time.perf_counter()
                self._do_update = False

    def control_send(self, data):
        if self.control_port is not None:
            self.control_socket.send_json(data)

    def get_default_title(self):
        self.title_parts =  sorted(list(set(self.title_parts)))
        title = ', '.join(self.title_parts)
        if title == '':
            title = 'Plot'
        return title


    def set_title(self, title=None):

        if title is None:
            title = self.get_default_title()

        self.setWindowTitle(title)


    def signal_received(self, topic, uuid, message):

        if uuid not in self.stores:
            self.stores[uuid] = DataSet(uuid)
        store = self.stores[uuid]

        for key, msg in message.items():
            if key == 'new_dataset':
                store.add_metadata(msg)
            elif key == 'clear_plot':
                del self.stores
                self.stores = {}

                for p in self.plots:
                    del p
                self.plots = []

                self.plot.clear()

            elif key == 'metadata':
                store.add_metadata(msg)

                if 'arrays' in msg:
                    arrays = msg['arrays']
                    for array_id, value in arrays.items():
                        store.get_array(array_id, arrays[array_id]['shape'])

            elif key == 'add_plot':
                data_arrays = msg.get('data_arrays', None)
                for ax in 'xyz':
                    array_info = msg.get(ax+'_info', None)
                    if array_info is not None:
                        self.title_parts.append(array_info['location'])

                        msg[ax] = store.get_array(
                            array_info['array_id'], array_info['shape'])
                        if data_arrays is not None:
                            data = data_arrays.get(
                                array_info['array_id'], None)
                            if data is not None:
                                msg[ax] = data

                pi = self.plot.add(**msg)

                msg['plot_item'] = pi
                self.plots.append(msg)

            elif key == 'data':
                if store.arrays == {}:
                    return
                ids_values = msg['values']
                loop_indices = tuple(msg['indices'])

                for array_id, value in ids_values.items():
                    store.store(array_id, loop_indices, value)
                    self._do_update = True

            elif key == 'finalize':
                self.save()
            elif key == 'set_title':
                self.setWindowTitle(msg)
            elif key == 'set_cmap':
                for dock in self.plot.subplots.keys():
                    self.plot.area.docks[dock].set_cmap(msg)


            else:
                pass
                # self.text_edit.append('Unknown message key %s' % key)
                # self.text_edit.append(str(msg))

    def update_labels(self):
        # for array_id, plot in self.plots.items():
        pass

    def save(self, filename=None):
        """
        Save current plot to filename, by default
        to the location corresponding to the default
        title.

        Args:
            filename (Optional[str]): Location of the file
        """
        default = "{}.png".format(self.get_default_title())
        filename = filename or default
        image = self.grab()
        self.control_send({'plot_saved': filename})

        i = 0
        while os.path.isfile(filename+'.png'):
            filename = filename + '_%d'%i
            i+=1
        image.save(filename, "PNG", 0)

    def closeEvent(self, event):
        self.zeromq_listener.running = False
        self.thread.quit()
        self.thread.wait()
        self.control_send({'client_losed': True})
        event.accept()


if __name__ == '__main__':
    import sys

    control_port = None
    if len(sys.argv) > 1:
        topic = str(sys.argv[1])
        port = str(sys.argv[2])
        control_port = str(sys.argv[3])
    else:
        port, topic = (8895, 'qcodes.plot.be6cc66678324187b344f1f5392dd927')

    mw = QtPlotWindow(topic=topic, port=port, control_port=control_port)


    mw.signal_received(topic='qcodes.plot.b819197931cd4b25b27c26d3eb347a27', uuid=None, message ={'set_cmap': 'hot'})

    mw.save()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
