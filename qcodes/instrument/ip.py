"""Ethernet instrument driver class based on sockets."""
import socket
import logging
from typing import Dict, Sequence, Optional

from .base import Instrument

log = logging.getLogger(__name__)


class IPInstrument(Instrument):

    r"""
    Bare socket ethernet instrument implementation.

    Before using the IPInstrument you should strongly consider if you can
    use Visa over raw sockets connecting to an address in the form:
    `TCPIP[board]::host address::port::SOCKET`

    Args:
        name (str): What this instrument is called locally.

        address (Optional[str]): The IP address or name. If not given on
            construction, must be provided before any communication.

        port (Optional[int]): The IP port. If not given on construction, must
            be provided before any communication.

        timeout (number): Seconds to allow for responses. Default 5.

        terminator (str): Character(s) to terminate each send. Default '\n'.

        read_terminator: Character(s) to look for at the end of each read.
            Defaults to None in which case only one recv is done
            Otherwise keeps reading until it gets the termination
            char(s).

        persistent (bool): Whether to leave the socket open between calls.
            Default True.

        write_confirmation (bool): Whether the instrument acknowledges writes
            with some response we should read. Default True.

        metadata (Optional[Dict]): additional static metadata to add to this
            instrument's JSON snapshot.

    See help for ``qcodes.Instrument`` for additional information on writing
    instrument subclasses.
    """

    def __init__(self, name, address=None, port=None, timeout=5,
                 terminator='\n', persistent=True, write_confirmation=True,
                 read_terminator=None,
                 **kwargs):
        super().__init__(name, **kwargs)

        self._address = address
        self._port = port
        self._timeout = timeout
        self._terminator = terminator
        self._read_terminator = read_terminator

        self._confirmation = write_confirmation

        self._ensure_connection = EnsureConnection(self)
        self._buffer_size = 1400

        self._socket = None

        self.set_persistent(persistent)

    @property
    def write_terminator(self):
        return self._terminator

    @write_terminator.setter
    def write_terminator(self, value):
        self._terminator = value

    @property
    def read_terminator(self):
        return self._read_terminator

    @read_terminator.setter
    def read_terminator(self, value):
        self._read_terminator = value

    def set_address(self, address=None, port=None):
        """
        Change the IP address and/or port of this instrument.

        Args:
            address (Optional[str]): The IP address or name.
            port (Optional[int, float]): The IP port.
        """
        if address is not None:
            self._address = address
        elif not hasattr(self, '_address'):
            raise TypeError('This instrument doesn\'t have an address yet, '
                            'you must provide one.')
        if port is not None:
            self._port = port
        elif not hasattr(self, '_port'):
            raise TypeError('This instrument doesn\'t have a port yet, '
                            'you must provide one.')

        self._disconnect()
        self.set_persistent(self._persistent)

    def set_persistent(self, persistent):
        """
        Change whether this instrument keeps its socket open between calls.

        Args:
            persistent (bool): Set True to keep the socket open all the time.
        """
        self._persistent = persistent
        if persistent:
            self._connect()
        else:
            self._disconnect()

    def flush_connection(self):
        self._recv()

    def _connect(self):

        if self._socket is not None:
            self._disconnect()

        try:
            log.info("Opening socket")
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            log.info("Connecting socket to {}:{}".format(self._address,
                                                         self._port))
            self._socket.connect((self._address, self._port))
            self.set_timeout(self._timeout)
        except ConnectionRefusedError:
            log.warning("Socket connection failed")
            self._socket.close()
            self._socket = None

    def _disconnect(self):
        if getattr(self, '_socket', None) is None:
            return
        log.info("Socket shutdown")
        self._socket.shutdown(socket.SHUT_RDWR)
        log.info("Socket closing")
        self._socket.close()
        log.info("Socket closed")
        self._socket = None

    def set_timeout(self, timeout=None):
        """
        Change the read timeout for the socket.

        Args:
            timeout (int, float): Seconds to allow for responses.
        """
        self._timeout = timeout

        if self._socket is not None:
            self._socket.settimeout(float(self._timeout))

    def set_terminator(self, terminator):
        r"""
        Change the write terminator to use.

        Args:
            terminator (str): Character(s) to terminate each send.
                Default '\n'.
        """
        self._terminator = terminator

    def _send(self, cmd):
        data = cmd + self._terminator
        log.debug(f"Writing {data} to instrument {self.name}")
        self._socket.sendall(data.encode())

    def _recv(self):
        result = b''
        while True:
            partresult = self._socket.recv(self._buffer_size)
            log.debug(f"Got {partresult} from instrument {self.name}")
            result += partresult
            if partresult == b'':
                log.warning("Got empty response from Socket recv() "
                            "Connection broken.")
            if self.read_terminator == None:
                break
            rtl = len(self.read_terminator)
            rtloc = result.find(self.read_terminator)
            if rtloc >= 0:
                if rtloc + rtl < len(result):
                    log.warning("Multiple (partial) results received. "
                                "All but the first result will be discarded. "
                                "Discarding {}".format(result[rtloc+rtl:]))
                result = result[0:rtloc]
                break
        return result.decode()

    def close(self):
        """Disconnect and irreversibly tear down the instrument."""
        self._disconnect()
        super().close()

    def write_raw(self, cmd):
        """
        Low-level interface to send a command that gets no response.

        Args:
            cmd (str): The command to send to the instrument.
        """

        with self._ensure_connection:
            self._send(cmd)
            if self._confirmation:
                self._recv()

    def ask_raw(self, cmd):
        """
        Low-level interface to send a command an read a response.

        Args:
            cmd (str): The command to send to the instrument.

        Returns:
            str: The instrument's response.
        """
        with self._ensure_connection:
            self._send(cmd)
            return self._recv()

    def __del__(self):
        self.close()

    def snapshot_base(self, update=False, params_to_skip_update: Optional[Sequence[str]] = None) -> Dict:
        """
        State of the instrument as a JSON-compatible dict (everything that
        the custom JSON encoder class :class:'qcodes.utils.helpers.NumpyJSONEncoder'
        supports).

        Args:
            update (bool): If True, update the state by querying the
                instrument. If False, just use the latest values in memory.
            params_to_skip_update: List of parameter names that will be skipped
                in update even if update is True. This is useful if you have
                parameters that are slow to update but can be updated in a
                different way (as in the qdac). If you want to skip the
                update of certain parameters in all snapshots, use the
                `snapshot_get`  attribute of those parameters: instead.

        Returns:
            dict: base snapshot
        """
        snap = super().snapshot_base(
            update=update,
            params_to_skip_update=params_to_skip_update)

        snap['port'] = self._port
        snap['confirmation'] = self._confirmation
        snap['address'] = self._address
        snap['terminator'] = self._terminator
        snap['timeout'] = self._timeout
        snap['persistent'] = self._persistent

        return snap


class EnsureConnection:

    """
    Context manager to ensure an instrument is connected when needed.

    Uses ``instrument._persistent`` to determine whether or not to close
    the connection immediately on completion.

    Args:
        instrument (IPInstrument): the instance to connect.
    """

    def __init__(self, instrument):
        self.instrument = instrument

    def __enter__(self):
        """Make sure we connect when entering the context."""
        if not self.instrument._persistent or self.instrument._socket is None:
            self.instrument._connect()

    def __exit__(self, type, value, tb):
        """Possibly disconnect on exiting the context."""
        if not self.instrument._persistent:
            self.instrument._disconnect()
