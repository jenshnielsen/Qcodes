""" Base class for the channel of an instrument """

from .base import Instrument
from .parameter import MultiParameter
from ..utils.metadata import Metadatable
from ..utils.helpers import full_class

class InstrumentChannel(Instrument):
    """
    Base class for a channel in an instrument

    Args:
        parent (Instrument): the instrument to which this channel should be attached

        name (str): the name of this channel

    Attributes:
        name (str): the name of this channel

        parameters (Dict[Parameter]): All the parameters supported by this channel.
            Usually populated via ``add_parameter``

        functions (Dict[Function]): All the functions supported by this channel.
            Usually populated via ``add_function``
    """

    def __init__(self, parent, name, **kwargs):
        # Initialize base classes of Instrument. We will overwrite what we want to do
        # in the Instrument initializer
        super(Instrument, self).__init__(**kwargs)

        self.parameters = {}
        self.functions = {}

        self.name = "{}_{}".format(parent.name, str(name))
        self._meta_attrs = ['name']

        self._parent = parent

    def __repr__(self):
        """Custom repr to give parent information"""
        return '<{}: {} of {}: {}>'.format(type(self).__name__, self.name,
            type(self._parent).__name__, self._parent.name)

    # We aren't a member of the global list of instruments, don't try and remove ourself
    def __del__(self):
        """ Does nothing for an instrument channel """
        pass

    def close(self):
        """ Doesn't make sense to just close a channel by default, raise NotImplemented """
        raise NotImplemented("Can't close a channel. Close my parent instead.")

    @classmethod
    def record_instance(cls, instance):
        """ Instances should not be recorded for channels. This should happen for the parent instrument. """
        pass

    @classmethod
    def instances(cls):
        """ Instances should not be recorded for channels. This should happen for the parent instrument. """
        pass

    @classmethod
    def remove_instances(cls, instance):
        """ It doesn't make sense to remove a channel from an instrument, raise NotImplemented"""
        raise NotImplemented("Can't remove a channel.")

    # This method doesn't make sense for a channel, raise NotImplemented
    @classmethod
    def find_instruments(cls, name, instrument_class=None):
        raise NotImplemented("Can't find instruments in a channel")

    # Pass any commands to read or write from the instrument up to the parent
    def write(self, cmd):
        return self._parent.write(cmd)
    def write_raw(self, cmd):
        return self._parent.write_raw(cmd)

    def ask(self, cmd):
        return self._parent.ask(cmd)
    def ask_raw(self, cmd):
        return self._parent.ask_raw(cmd)

class ChannelList(Metadatable):
    """
    Container for channelized parameters that allows for sweeps over all channels, as well
    as addressing of individual channels.

    Args:
        parent (Instrument): the instrument to which this channel should be attached

        name (string): the name of the channel list

        chan_type (InstrumentChannel): the type of channel contained within this list

        chan_list (Iterable[chan_type]): An optional iterable of channels of type chan_type.
            This will create a list and immediately lock the ChannelList.

    Attributes:
        parameters (Dict[Parameter]): All the parameters supported by this group of channels.

        functions (Dict[Function]): All the functions supported by this group of channels
    """

    def __init__(self, parent, name, chan_type, chan_list=None):
        super().__init__()

        self._parent = parent
        self._name = name
        if type(chan_type) != type or not issubclass(chan_type, InstrumentChannel):
            print(chan_type, InstrumentChannel)
            raise ValueError("Channel Lists can only hold instances of type InstrumentChannel")
        self._chan_type = chan_type

        # If a list of channels is not provided, define a list to store channels. 
        # This will eventually become a locked tuple.
        if chan_list is None:
            self._locked = False
            self._channels = []
        else:
            self._locked = True
            self._channels = tuple(chan_list)
            if not all(isinstance(chan, chan_type) for chan in self._channels):
                raise TypeError("All items in this channel list must be of type {}.".format(chan_type.__name__))

    def __getitem__(self, i):
        """
        Return either a single channel, or a new ChannelList containing only the specified channels

        Args:
            i (int/slice): Either a single channel index or a slice of channels to get
        """
        if isinstance(i, slice):
            return ChannelList(self._parent, self._name, self._chan_type, self._channels[i])
        return self._channels[i]

    def __iter__(self):
        return iter(self._channels)

    def __len__(self):
        return len(self._channels)

    def __repr__(self):
        return "ChannelList({!r}, {}, {!r})".format(self._parent, self._chan_type.__name__, self._channels)

    def __add__(self, other):
        """
        Return a new channel list containing the channels from both ChannelList self and r.

        Both channel lists must hold the same type and have the same parent.

        Args:
            other(ChannelList): Right argument to add.
        """
        if not isinstance(self, ChannelList) or not isinstance(other, ChannelList):
            raise TypeError("Can't add objects of type {} and {} together".format(
                type(self).__name__, type(other).__name__))
        if self._chan_type != other._chan_type:
            raise TypeError("Both l and r arguments to add must contain channels of the same type."
                " Adding channels of type {} and {}.".format(self._chan_type.__name__, 
                    other._chan_type.__name__))
        if self._parent != other._parent:
            raise ValueError("Can only add channels from the same parent together.")

        return ChannelList(self._parent, self._name, self._chan_type, self._channels + other._channels)

    def append(self, object):
        """
        When initially constructing the channel list, a new channel to add to the end of the list

        Args:
            object(chan_type): New channel to add to the list.
        """
        if self._locked:
            raise AttributeError("Cannot append to a locked channel list")
        if not isinstance(object, self._chan_type):
            raise TypeError("All items in a channel list must be of the same type."
                " Adding {} to a list of {}.".format(type(object).__name__, self._chan_type.__name__))
        return self._channels.append(object)

    def extend(self, objects):
        """
        Insert an iterable of objects into the list of channels.

        Args:
            objects(Iterable[chan_type]): A list of objects to add into the ChannelList.
        """
        if self._locked:
            raise AttributeError("Cannot extend a locked channel list")
        if not all(isinstance(object, self._chan_type) for object in objects):
            raise TypeError("All items in a channel list must be of the same type.")
        return self._channels.extend(objects)

    def index(self, object):
        """
        Return the index of the given object

        Args:
            object(chan_type): The object to find in the channel list.
        """
        return self._channels.index(object)

    def insert(self, index, object):
        """
        Insert an object into the channel list at a specific index.

        Args:
            index(int): Index to insert object.

            object(chan_type): Object of type chan_type to insert.
        """
        if self._locked:
            raise AttributeError("Cannot insert into a locked channel list")
        if not isinstance(object, self._chan_type):
            raise TypeError("All items in a channel list must be of the same type."
                " Adding {} to a list of {}.".format(type(object).__name__, self._chan_type.__name__))
        return self._channels.insert(index, object)

    def lock(self):
        """
        Lock the channel list. Once this is done, the channel list is converted to a tuple
        and any future changes to the list are prevented.
        """
        if self._locked:
            return
        self._channels = tuple(self._channels)
        self._locked = True

    def snapshot_base(self, update=False):
        """
        State of the instrument as a JSON-compatible dict.

        Args:
            update (bool): If True, update the state by querying the
                instrument. If False, just use the latest values in memory.

        Returns:
            dict: base snapshot
        """
        snap = {'channels': dict((chan.name, chan.snapshot(update=update))
                                   for chan in self._channels),
                '__class__': full_class(self),
                }
        return snap

    def __getattr__(self, name):
        """
        Return a multi-channel function or parameter that we can use to get or set all items
        in a channel list simultaneously.

        Params:
            name(str): The name of the parameter or function that we want to operate on.
        """
        # Check if this is a valid parameter
        if name in self._channels[0].parameters:
            # We need to construct a MultiParameter object to get each of the 
            # values our of each parameter in our list
            names = tuple("{}.{}".format(chan.name, name) for chan in self._channels)
            shapes = tuple(() for chan in self._channels) #TODO: Pull shapes intelligently
            labels = tuple(chan.parameters[name].label for chan in self._channels)
            units = tuple(chan.parameters[name].unit for chan in self._channels)

            param = MultiChannelInstrumentParameter(self._channels, name,
                name="Multi_{}".format(name), 
                names=names, shapes=shapes, instrument=self._parent, 
                labels=labels, units=units)
            return param

        # Check if this is a valid function
        if name in self._channels[0].functions:
            # We want to return a reference to a function that would call the function
            # for each of the channels in turn.
            def multi_func(*args, **kwargs):
                for chan in self._channels:
                    chan.functions[name](*args, **kwargs)
            return multi_func

        raise AttributeError('\'{}\' object has no attribute \'{}\''.format(self.__class__.__name__, name))

class MultiChannelInstrumentParameter(MultiParameter):
    """
    Parameter to get or set multiple channels simultaneously.

    Will normally be created by a ChannelList and not directly by anything else.

    Args:
        channels(list[chan_type]): A list of channels which we can operate on simultaneously.

        param_name(str): Name of the multichannel parameter
    """
    def __init__(self, channels, param_name, *args, **kwargs):
        self._channels = channels
        self._param_name = param_name
        super().__init__(*args, **kwargs)

    def get(self):
        """
        Return a tuple containing the data from each of the channels in the list
        """
        return tuple(chan.parameters[self._param_name].get() for chan in self._channels)