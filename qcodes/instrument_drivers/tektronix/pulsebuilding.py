# implementing what Filip and Natalie asked for...
#
# In this iteration, we do it in a horribly object-oriented way

import logging
from inspect import signature
import functools as ft
import numpy as np
import matplotlib.pyplot as plt
plt.ion()

log = logging.getLogger(__name__)


class PulseAtoms:
    """
    A class full of static methods.
    The basic pulse shapes.

    Any pulse shape function should return a list or an np.array
    and have SR, duration as its final two arguments.
    """

    @staticmethod
    def sine(freq, ampl, off, SR, dur):
        time = np.linspace(0, dur, dur*SR)
        freq *= 2*np.pi
        return (ampl*np.sin(freq*time)+off)

    @staticmethod
    def ramp(slope, offset, SR, dur):
        time = np.linspace(0, dur, dur*SR)
        return (slope*time+offset)

    @staticmethod
    def waituntil(dummy, SR, dur):
        # for internal call signature consistency, a dummy variable is needed
        return (np.zeros(dur*SR))

    @staticmethod
    def gaussian(ampl, sigma, mu, offset, SR, dur):
        """
        Returns a Gaussian of integral ampl (when offset==0)

        Is by default centred in the middle of the interval
        """
        time = np.linspace(0, dur, dur*SR)
        centre = dur/2
        baregauss = np.exp((-(time-mu-centre)**2/(2*sigma**2)))
        normalisation = 1/np.sqrt(2*sigma**2*np.pi)
        return ampl*baregauss*normalisation+offset


class BluePrint():
    """
    The class to contain the bluePrint of an element.

    Several bluePrints may be passed to the elementBuilder, which turns
    them into numpy arrays.
    """

    def __init__(self, funlist, argslist, namelist, tslist=None,
                 marker1=None, marker2=None, segmentmarker1=None,
                 segmentmarker2=None):
        """
        Create a BluePrint instance.

        Args:
            funlist (list): List of functions
            argslist (list): List of tuples of arguments
            namelist (list): List of names for the functions
            tslist (list): List of timesteps for each segment
            marker1 (list): List of marker1 specification tuples
            marker2 (list): List of marker2 specifiation tuples

        Returns:
            BluePrint
        """
        # TODO: validate input

        # Validation
        #
        # Are the lists of matching lengths?
        lenlist = [len(funlist), len(argslist), len(namelist)]
        if tslist is not None:
            lenlist.append(len(tslist))
        if len(set(lenlist)) is not 1:
            raise ValueError('All input lists must be of same length. '
                             'Received lengths: {}'.format(lenlist))
        # Are the names valid names?
        for name in namelist:
            if not isinstance(name, str):
                raise ValueError('All segment names must be strings. '
                                 'Received {}'.format(name))
            elif name is not '':
                if name[-1].isdigit():
                    raise ValueError('Segment names are not allowed to end'
                                     ' in a number. {} is '.format(name) +
                                     'therefore not a valid name.')

        self._funlist = funlist

        # Make special functions live in the funlist but transfer their names
        # to the namelist
        # Infer names from signature if not given, i.e. allow for '' names
        for ii, name in enumerate(namelist):
            if isinstance(funlist[ii], str):
                namelist[ii] = funlist[ii]
            elif name == '':
                namelist[ii] = funlist[ii].__name__

        # Allow single arguments to be given as not tuples
        for ii, args in enumerate(argslist):
            if not isinstance(args, tuple):
                argslist = (args)
        self._argslist = argslist

        self._namelist = namelist
        namelist = self._make_names_unique(namelist)

        if tslist is None:
            self._tslist = [1]*len(namelist)
        else:
            self._tslist = tslist

        # initialise markers
        if marker1 is None:
            self.marker1 = []
        else:
            self.marker1 = marker1
        if marker2 is None:
            self.marker2 = []
        else:
            self.marker2 = marker2
        if segmentmarker1 is None:
            self._segmark1 = [(0, 0)]*len(funlist)
        else:
            self._segmark1 = segmentmarker1
        if segmentmarker2 is None:
            self._segmark2 = [(0, 0)]*len(funlist)
        else:
            self._segmark2 = segmentmarker2

    @staticmethod
    def _basename(string):
        """
        Remove trailing numbers from a string. (currently removes all numbers)
        """
        if not(string[-1].isdigit()):
            return string
        else:
            counter = 0
            for ss in string[::-1]:
                if ss.isdigit():
                    counter += 1
                else:
                    break
            return string[:-counter]

        # lst = [letter for letter in string if not letter.isdigit()]
        # return ''.join(lst)

    @staticmethod
    def _make_names_unique(lst):
        """
        Make all strings in the input list unique
        by appending numbers to reoccuring strings

        Args:
            lst (list): List of strings. Intended for the _namelist

        """

        baselst = [BluePrint._basename(lstel) for lstel in lst]
        uns = np.unique(baselst)

        for un in uns:
            inds = [ii for ii, el in enumerate(baselst) if el == un]
            for ii, ind in enumerate(inds):
                # Do not append numbers to the first occurence
                if ii == 0:
                    lst[ind] = '{}'.format(un)
                else:
                    lst[ind] = '{}{}'.format(un, ii+1)

        return lst

    @property
    def length(self):
        """
        Returns the number of assigned time steps currently in the blueprint.
        """
        return len(self._tslist)

    def showPrint(self):
        """
        Pretty-print the contents of the BluePrint. Not finished.
        """
        # TODO: tidy up this method

        lzip = zip(self._namelist, self._funlist, self._argslist, self._tslist)
        for ind, (name, fun, args, ts) in enumerate(lzip):
            print('Segment {}: {}, {}, {}, {}'.format(ind+1,
                                                      name, fun, args, ts))

    def changeArg(self, name, arg, value, replaceeverywhere=False):
        """
        Change an argument of one or more of the functions in the blueprint.

        Args:
            name (str): The name of the segment in which to change an argument
            arg (Union[int, str]): Either the position (int) or name (str) of
                the argument to change
            value (Union[int, float]): The new value of the argument
            replaceeverywhere (bool): If True, the same argument is overwritten
                in ALL segments where the name matches. E.g. 'gaussian1' will
                match 'gaussian', 'gaussian2', etc. If False, only the segment
                with exact name match gets a replacement.

        Raises:

        """
        # TODO: is there any reason to use tuples internally?
        # TODO: add input validation

        if replaceeverywhere:
            basename = BluePrint._basename
            name = basename(name)
            nmlst = self._namelist
            replacelist = [nm for nm in nmlst if basename(nm) == name]
        else:
            replacelist = [name]

        for name in replacelist:

            position = self._namelist.index(name)
            function = self._funlist[position]
            sig = signature(function)

            # Validation
            if isinstance(arg, str):
                if arg not in sig.parameters:
                    raise ValueError('No such argument of function '
                                     '{}.'.format(function.__name__) +
                                     'Has arguments '
                                     '{}.'.format(sig.parameters))
            if isinstance(arg, int) and arg > len(sig.parameters):
                raise ValueError('No argument {} '.format(arg) +
                                 'of function {}.'.format(function.__name__) +
                                 'Has {} '.format(len(sig.parameters)) +
                                 'arguments.')

            # allow the user to input single values instead of (val,)
            no_of_args = len(self._argslist[position])
            if not isinstance(value, tuple) and no_of_args == 1:
                value = (value,)

            if isinstance(arg, str):
                for ii, param in enumerate(sig.parameters):
                    if arg == param:
                        arg = ii
                        break

            # Mutating the immutable...
            larg = list(self._argslist[position])
            larg[arg] = value
            self._argslist[position] = tuple(larg)

    def setSegmentMarker(self, name, specs, markerID):
        """
        Bind a marker to a specific segment.

        Args:
            name (str): Name of the segment
            specs (tuple): Marker specification tuple, (delay, duration),
                where the delay is relative to the segment start
            markerID (int): Which marker channel to output on. Must be 1 or 2.
        """
        if markerID not in [1, 2]:
            raise ValueError('MarkerID must be either 1 or 2.'
                             ' Received {}.'.format(markerID))

        markerselect = {1: self._segmark1, 2: self._segmark2}
        position = self._namelist.index(name)

        # TODO: Do we need more than one bound marker per segment?
        markerselect[markerID][position] = specs

    def removeSegmentMarker(self, name, markerID):
        """
        Remove a bound marker from a specific segment

        Args:
            name (str): Name of the segment
            markerID (int): Which marker channel to remove from (1 or 2).
            number (int): The number of the marker, in case several markers are
                bound to one element. Default: 1 (the first marker).
        """
        if markerID not in [1, 2]:
            raise ValueError('MarkerID must be either 1 or 2.'
                             ' Received {}.'.format(markerID))

        markerselect = {1: self._segmark1, 2: self._segmark2}
        position = self._namelist.index(name)
        markerselect[markerID][position] = (0, 0)

    def changeDuration(self, name, n):
        """
        Change the duration (in number of timesteps) of the blueprint segment
        with the specified name.

        Args:
            name (str): The name of a segment of the blueprint.
            n (int): The number of timesteps for this segment to last.
        """
        position = self._namelist.index(name)

        if self._funlist[position] == 'waituntil':
            raise ValueError('Special function waituntil can not last more' +
                             'than one time step')

        n_is_whole_number = float(n).is_integer()
        if not (n >= 1 and n_is_whole_number):
            raise ValueError('n must be a whole number strictly' +
                             ' greater than 0.')

        self._tslist[position] = n

    def copy(self):
        """
        Returns a copy of the BluePrint
        """

        # Needed because of input validation in __init__
        namelist = [self._basename(name) for name in self._namelist.copy()]

        return BluePrint(self._funlist.copy(),
                         self._argslist.copy(),
                         namelist,
                         self._tslist.copy(),
                         self.marker1.copy(),
                         self.marker2.copy(),
                         self._segmark1.copy(),
                         self._segmark2.copy())

    def insertSegment(self, pos, func, args=(), name=None, ts=1):
        """
        Insert a segment into the bluePrint.

        Args:
            pos (int): The position at which to add the segment. Counts like
                a python list; 0 is first, -1 is last. Values below -1 are
                not allowed, though.
            func (function): Function describing the segment. Must have its
               duration as the last argument (unless its a special function).
            args (tuple): Tuple of arguments BESIDES duration. Default: ()
            name (str): Name of the segment. If none is given, the segment
                will receive the name of its function, possibly with a number
                appended.
            ts (int): Number of time segments this segment should last.
                Default: 1.
        """

        # allow users to input single values
        if not isinstance(args, tuple):
            args = (args,)

        if pos < -1:
            raise ValueError('Position must be strictly larger than -1')

        if name is None:
            name = func.__name__
        elif isinstance(name, str):
            if len(name) > 0:
                if name[-1].isdigit():
                    raise ValueError('Segment name must not end in a number')

        if pos == -1:
            self._namelist.append(name)
            self._namelist = self._make_names_unique(self._namelist)
            self._funlist.append(func)
            self._argslist.append(args)
            self._tslist.append(ts)
            self._segmark1.append((0, 0))
            self._segmark2.append((0, 0))
        else:
            self._namelist.insert(pos, name)
            self._namelist = self._make_names_unique(self._namelist)
            self._funlist.insert(pos, func)
            self._argslist.insert(pos, args)
            self._tslist.insert(pos, ts)
            self._segmark1.insert(pos, (0, 0))
            self._segmark2.insert(pos, (0, 0))

    def removeSegment(self, name):
        """
        Remove the specified segment from the blueprint.

        Args:
            name (str): The name of the segment to remove.
        """
        position = self._namelist.index(name)

        del self._funlist[position]
        del self._argslist[position]
        del self._tslist[position]
        del self._namelist[position]
        del self._segmark1[position]
        del self._segmark2[position]

    def _validateDurations(self, durations):
        """
        Checks wether the number of durations matches the number of segments
        and their specified lengths (including 'waituntils')

        Args:
            durations (list): List of durations

        Raises:
            ValueError: If the length of durations does not match the
                blueprint.
        """
        no_of_waits = self._funlist.count('waituntil')
        if sum(self._tslist) != len(durations)+no_of_waits:
            raise ValueError('The specified timesteps do not match the number '
                             'of durations. '
                             '({} and {})'.format(sum(self._tslist),
                                                  len(durations) +
                                                  no_of_waits))

    def getLength(self, SR, durations):
        """
        Calculate the length of the BluePrint, where it to be forged with
        the specified durations.

        Args:
            durations (list): List of durations

        Returns:
            int: The number of points of the element

        Raises:
            ValueError: If the length of durations does not match the
                blueprint.
        """
        self._validateDurations(durations)

        no_of_waits = self._funlist.count('waituntil')
        waitpositions = [ii for ii, el in enumerate(self._funlist)
                         if el == 'waituntil']

        # TODO: This is reuse of elementBuilder code... Refactor?
        for nw in range(no_of_waits):
            pos = waitpositions[nw]
            elapsed_time = sum(durations[:pos])
            wait_time = argslist[pos][0]
            dur = wait_time - elapsed_time
            if dur < 0:
                raise ValueError('Inconsistent timing. Can not wait until ' +
                                 '{} at position {}.'.format(wait_time, pos) +
                                 ' {} elapsed already'.format(elapsed_time))
            else:
                durations.insert(pos, dur)

        return(sum(durations)*SR)

    def __add__(self, other):
        """
        Add two BluePrints. The second argument is appended to the first
        and a new BluePrint is returned.

        Args:
            other (BluePrint): A BluePrint instance

        Returns:
            BluePrint: A new blueprint.

        Raises:
            ValueError: If the input is not a BluePrint instance
        """
        if not isinstance(other, BluePrint):
            raise ValueError("""
                             BluePrint can only be added to another Blueprint.
                             Received an object of type {}
                             """.format(type(other)))

        nl = [self._basename(name) for name in self._namelist]
        nl += [self._basename(name) for name in other._namelist]
        al = self._argslist + other._argslist
        fl = self._funlist + other._funlist
        tl = self._tslist + other._tslist
        m1 = self.marker1 + other.marker1
        m2 = self.marker2 + other.marker2

        return BluePrint(fl, al, nl, tl, m1, m2)

    def __eq__(self, other):
        """
        Compare two blueprints. They are the same iff all
        lists are identical.

        Args:
            other (BluePrint): A BluePrint instance

        Returns:
            bool: whether the two blueprints are identical

        Raises:
            ValueError: If the input is not a BluePrint instance
        """
        if not isinstance(other, BluePrint):
            raise ValueError("""
                             Blueprint can only be compared to another
                             Blueprint.
                             Received an object of type {}
                             """.format(type(other)))

        if not self._namelist == other._namelist:
            return False
        if not self._funlist == other._funlist:
            return False
        if not self._argslist == other._argslist:
            return False
        if not self._tslist == other._tslist:
            return False
        if not self.marker1 == other.marker2:
            return False
        if not self.marker2 == other.marker2:
            return False
        return True


class Sequence:
    """
    Object representing a sequence
    """

    def __init__(self):
        """
        Not much to see here...
        """

        # the internal data structure, a list of lists of tuples
        # The outer list represents channels, the next a sequence and finally
        # tuples of (bluedprint, durations)
        # self._data = [[(None, None)]]

        # the internal data structure, a dict with tuples as keys and values
        # the key is (channel, sequence position), the value is
        # (blueprint, durations)
        self._data = {}

        # Here goes the sequencing info. Key: position, value: list
        # where list = [wait, nrep, jump, goto]
        self._sequencing = {}

        # The dictionary to store AWG settings
        # Keys will include:
        # 'SR', 'channelXampl'
        self._awgspecs = {}

    def setSequenceSettings(self, pos, wait, nreps, jump, goto):
        """
        Set the sequence setting for the sequence element at pos.

        Args:
            pos (int): The sequence element (counting from 1)
            wait (int): The wait state specifying whether to wait for a
                trigger. 0: OFF, don't wait, 1: ON, wait.
            nreps (int): Number of repetitions. 0 corresponds to infinite
                repetitions
            jump (int): Jump target, the position of a sequence element
            goto (int): Goto target, the position of a sequence element
        """

        # Validation (some validation 'postponed' and put in checkConsistency)
        if wait not in [0, 1]:
            raise ValueError('Can not set wait to {}.'.format(wait) +
                             ' Must be either 0 or 1.')

        self._sequencing[pos] = [wait, nreps, jump, goto]

    def setSR(self, SR):
        """
        Set the sample rate for the sequence
        """
        self._awgspecs['SR'] = SR

    def setChannelVoltageRange(self, channel, ampl, offset):
        """
        Assign the physical voltages of the channel. This is used when making
        output for .awg files. The corresponding parameters in the QCoDeS
        AWG5014 driver are called chXX_amp and chXX_offset. Please ensure that
        the channel in question is indeed in ampl/offset mode and not in
        high/low mode.

        Args:
            channel (int): The channel number
            ampl (float): The channel peak-to-peak amplitude (V)
            offset (float): The channel offset (V)
        """
        keystr = 'channel{}_amplitude'.format(channel)
        self._awgspecs[keystr] = ampl
        keystr = 'channel{}_offset'.format(channel)
        self._awgspecs[keystr] = offset

    def setChannelDelay(self, channel, delay):
        """
        Assign a delay to a channel. This is used when making output for .awg
        files. Use the delay to compensate for cable length differences etc.
        Zeros are prepended to the waveforms to delay them and correspondingly
        appended to non (or less) delayed channels.

        Args:
            channel (int): The channel number
            delay (float): The required delay (s)

        Raises:
            ValueError: If a non-integer or non-non-negative channel number is
                given.
        """

        if not isinstance(channel, int) or channel < 1:
            raise ValueError('{} is not a valid '.format(channel) +
                             'channel number.')

        self._awgspecs['channel{}_delay'.format(channel)] = delay

    def addElement(self, channel, position, blueprint, durations):
        """
        Add an element to the sequence

        Args:
            channel (int): The channel to add the element to (lowest: 1)
            position (int): The sequence position of the element (lowest: 1)
            blueprint (BluePrint): A blueprint object
            durations (list): A list of durations

        Raises:
            ValueError: If the blueprint and the durations can not be forged.
                A descriptive error message is issued.
        """

        # Validation
        blueprint._validateDurations(durations)

        # Data mutation
        self._data.update({(channel, position): (blueprint, durations)})

    def checkConsistency(self, verbose=False):
        """
        Checks wether the sequence can be built, i.e. if all channels with
        elements on them have elements of the same length in the same places
        """
        # TODO: Give helpful info if the check fails

        try:
            SR = self._awgspecs['SR']
        except KeyError:
            raise KeyError('No sample rate specified. Can not perform check')

        # First check that all channels have elements in the same positions
        chans = set([tup[0] for tup in self._data.keys()])
        positions = [[]]*len(chans)
        for ind, chan in enumerate(chans):
            positions[ind-1] = [t[1] for t in self._data.keys()
                                if t[0] == chan]
            positions[ind-1] = set(positions[ind-1])
        if not positions.count(positions[0]) == len(positions):
            failmssg = ('checkConsistency failed: not the same number of '
                        'elements on all channels')
            log.info(failmssg)
            if verbose:
                print(failmssg)
            return False

        # Then check that all channels specify all sequence elements
        if not positions[0] == set(range(1, len(positions[0])+1)):
            failmssg = ('checkConsistency failed: Missing sequence element(s)')
            log.info(failmssg)
            if verbose:
                print(failmssg)
            return False

        # Finally, check that all elements have the same length
        for pos in positions[0]:
            lens = []
            for chan in chans:
                bp = self._data[(chan, pos)][0]
                durs = self._data[(chan, pos)][1]
                lens.append(bp.getLength(SR, durs))
            if not lens.count(lens[0]) == len(lens):
                failmssg = ('checkConsistency failed: elements at position'
                            ' {} are not of same length'.format(pos) +
                            ' Lengths are (no. of points): {}'.format(lens))
                log.info(failmssg)
                if verbose:
                    print(failmssg)
                return False

        # If all three tests pass...
        return True

    def setSeveralElements(self, channel, baseblueprint, variable, durations,
                           iterable):
        """
        Set all (sub)elements on the specified channel to be variations of
        a basic blueprint. Note: this overwrites any (sub)elements that were
        previously assigned to the relevant positions.

        Args:
            channel (int): The channel to assign the (sub)elements to.
            baseblueprint (BluePrint): The basic blueprint.
            variable (tuple): A tuple specifying the parameter to vary. Must
                be either (name (str), arg (str)) or (name (str), pos (int),
                where name is the name of the segment in the blueprint and
                arg/pos is the name/position of the argument to change.
            durations (list): List of durations
            iterable (iterable): An iterable object containing the argument
                values. The first value will be the value of the first
                element.
        """

        # Validation
        try:
            baseblueprint.changeArg(variable[0], variable[1], 0)
        except ValueError as err:
            raise ValueError('Can not make specified variation. '
                             'Got the following error message: {}'.format(err))

        # Make the sequence by adding blueprints one-by-one
        for pos, value in enumerate(iterable):
            bp = baseblueprint.copy()
            bp.changeArg(variable[0], variable[1], value)
            self.addElement(channel, pos+1, bp, durations)

    @property
    def lenght(self):
        """
        Returns the current number of specified sequence elements
        """
        chans = set([tup[0] for tup in self._data.keys()])
        seqlen = len([t for t in self._data.keys() if t[0] == list(chans)[0]])
        return seqlen

    def plotSequence(self):
        """
        Visualise the sequence

        """
        if not self.checkConsistency():
            raise ValueError('Can not plot sequence: Something is '
                             'inconsistent. Please run '
                             'checkConsistency(verbose=True) for more details')

        chans = set([tup[0] for tup in self._data.keys()])

        # First forge all elements
        SR = self._awgspecs['SR']
        seqlen = len([t for t in self._data.keys() if t[0] == list(chans)[0]])
        elements = []  # the forged elements
        for pos in range(1, seqlen+1):
            blueprints = [self._data[(chan, pos)][0] for chan in chans]
            durations = [self._data[(chan, pos)][1] for chan in chans]
            elements.append(elementBuilder(blueprints, SR, durations,
                                           chans, returnnewdurs=True))

        # Now get the dimensions. Since the check passed, we may be slobby
        chans = set([tup[0] for tup in self._data.keys()])
        seqlen = len([t for t in self._data.keys() if t[0] == list(chans)[0]])

        # Then figure out the figure scalings
        chanminmax = [[np.inf, -np.inf]]*len(chans)
        for chanind, chan in enumerate(chans):
            for pos in range(seqlen):
                wfmdata = elements[pos][chan][0]
                (thismin, thismax) = (wfmdata.min(), wfmdata.max())
                if thismin < chanminmax[chanind][0]:
                    chanminmax[chanind] = [thismin, chanminmax[chanind][1]]
                if thismax > chanminmax[chanind][1]:
                    chanminmax[chanind] = [chanminmax[chanind][0], thismax]

        fig, axs = plt.subplots(len(chans), seqlen)

        # ...and do the plotting
        for chanind, chan in enumerate(chans):
            for pos in range(seqlen):
                # 1 by N arrays are indexed differently than M by N arrays
                # and 1 by 1 arrays are not arrays at all...
                if len(chans) == 1 and seqlen > 1:
                    ax = axs[pos]
                if len(chans) > 1 and seqlen == 1:
                    ax = axs[chanind]
                if len(chans) == 1 and seqlen == 1:
                    ax = axs
                if len(chans) > 1 and seqlen > 1:
                    ax = axs[chanind, pos]

                wfm = elements[pos][chan][0]
                m1 = elements[pos][chan][1]
                m2 = elements[pos][chan][2]
                time = elements[pos][chan][3]
                newdurs = elements[pos][chan][4]

                # waveform
                ax.plot(time, wfm, lw=3, color=(0.6, 0.4, 0.3), alpha=0.4)
                ymax = chanminmax[chanind][1]
                ymin = chanminmax[chanind][0]
                yrange = ymax - ymin
                ax.set_ylim([ymin-0.05*yrange, ymax+0.2*yrange])

                # marker1 (red, on top)
                y_m1 = ymax+0.15*yrange
                marker_on = np.ones_like(m1)
                marker_on[m1 == 0] = np.nan
                marker_off = np.ones_like(m1)
                ax.plot(time, y_m1*marker_off, color=(0.6, 0.1, 0.1),
                        alpha=0.2, lw=2)
                ax.plot(time, y_m1*marker_on, color=(0.6, 0.1, 0.1),
                        alpha=0.6, lw=2)

                # marker 2 (blue, below the red)
                y_m2 = ymax+0.10*yrange
                marker_on = np.ones_like(m2)
                marker_on[m2 == 0] = np.nan
                marker_off = np.ones_like(m2)
                ax.plot(time, y_m2*marker_off, color=(0.1, 0.1, 0.6),
                        alpha=0.2, lw=2)
                ax.plot(time, y_m2*marker_on, color=(0.1, 0.1, 0.6),
                        alpha=0.6, lw=2)

                # time step lines
                for dur in np.cumsum(newdurs):
                    ax.plot([dur, dur], [ax.get_ylim()[0],
                                         ax.get_ylim()[1]],
                            color=(0.312, 0.2, 0.33),
                            alpha=0.3)

                # remove excess space from the plot
                if not chanind+1 == len(chans):
                    ax.set_xticks([])
                if not pos == 0:
                    ax.set_yticks([])
                fig.subplots_adjust(hspace=0, wspace=0)

    def outputForAWGFile(self):
        """
        Returns an output matching the call signature of the 'make_*_awg_file'
        functions of the QCoDeS AWG5014 driver. One may then construct an awg
        file as follows (assuming that seq is the sequence object):

        make_awg_file(*seq.outputForAWGFile(), **kwargs)

        The outputForAWGFile applies all specified signal corrections.
          delay of channels
        """
        # TODO: implement corrections

        # Validation
        if not self.checkConsistency():
            raise ValueError('Can not generate output. Something is '
                             'inconsistent. Please run '
                             'checkConsistency(verbose=True) for more details')

        channels = set([tup[0] for tup in self._data.keys()])
        # We copy the data so that the state of the Sequence is left unaltered
        # by outputting for AWG
        data = self._data.copy()
        seqlen = len([t for t in data.keys() if t[0] == list(channels)[0]])
        if not list(self._sequencing.keys()) == list(range(1, seqlen+1)):
            raise ValueError('Can not generate output for .awg file; '
                             'incorrect sequencer information.')

        for chan in channels:
            ampkey = 'channel{}_amplitude'.format(chan)
            if ampkey not in self._awgspecs.keys():
                raise KeyError('No amplitude specified for channel '
                               '{}. Can not continue.'.format(chan))
            offkey = 'channel{}_offset'.format(chan)
            if offkey not in self._awgspecs.keys():
                raise KeyError('No offset specified for channel '
                               '{}. Can not continue.'.format(chan))

        # Apply channel delays. This is most elegantly done before forging.
        # Add waituntil at the beginning, update all waituntils inside, add a
        # zeros segment at the end.
        delays = []
        for chan in channels:
            try:
                delays.append(self._awgspecs['channel{}_delay'.format(chan)])
            except KeyError:
                delays.append(0)
        maxdelay = max(delays)
        seqlen = len([t for t in data.keys() if t[0] == list(channels)[0]])
        for pos in range(1, seqlen+1):
            for chanind, chan in enumerate(channels):
                # it is also necessary to copy the blueprint
                blueprint = data[(chan, pos)][0].copy()
                delay = delays[chanind]
                # update existing waituntils
                for segpos in range(blueprint.length):
                    if isinstance(blueprint._funlist[segpos], str):
                        if 'waituntil' in blueprint._funlist[segpos]:
                            oldwait = blueprint._argslist[segpos](0)
                            blueprint._argslist[segpos] = (oldwait+delay,)
                # insert delay before the waveform
                blueprint.insertSegment(0, 'waituntil', (delay,), 'waituntil')
                # add zeros at the end
                blueprint.insertSegment(-1, PulseAtoms.ramp, (0, 0))
                newdurs = data[(chan, pos)][1]+[maxdelay-delay]
                data[(chan, pos)] = (blueprint, newdurs)

        # Now forge all the elements as specified
        SR = self._awgspecs['SR']
        seqlen = len([t for t in data.keys() if t[0] == list(channels)[0]])
        elements = []  # the forged elements
        for pos in range(1, seqlen+1):
            blueprints = [data[(chan, pos)][0] for chan in channels]
            durations = [data[(chan, pos)][1] for chan in channels]
            elements.append(elementBuilder(blueprints, SR, durations,
                                           channels))

        # Apply channel scaling
        # We must rescale to the interval -1, 1 where 1 is ampl/2+off and -1 is
        # -ampl/2+off.
        def rescaler(val, ampl, off):
            return val/ampl*2-off
        for pos in range(1, seqlen+1):
            element = elements[pos-1]
            for chan in channels:
                ampl = self._awgspecs['channel{}_amplitude'.format(chan)]
                off = self._awgspecs['channel{}_offset'.format(chan)]
                wfm = element[chan][0]
                # check whether the wafeform voltages can be realised
                if wfm.max() > ampl/2+off:
                    raise ValueError('Waveform voltages exceed channel range '
                                     'on channel {}'.format(chan) +
                                     ' sequence element {}.'.format(pos) +
                                     ' {} > {}!'.format(wfm.max(), ampl/2+off))
                if wfm.min() < -ampl/2+off:
                    raise ValueError('Waveform voltages exceed channel range '
                                     'on channel {}'.format(chan) +
                                     ' sequence element {}. '.format(pos) +
                                     '{} < {}!'.format(wfm.min(), -ampl/2+off))
                wfm = rescaler(wfm, ampl, off)

        # Finally cast the lists into the shapes required by the AWG driver
        waveforms = [[] for dummy in range(len(channels))]
        m1s = [[] for dummy in range(len(channels))]
        m2s = [[] for dummy in range(len(channels))]
        nreps = []
        trig_waits = []
        goto_states = []
        jump_tos = []

        for pos in range(1, seqlen+1):
            for chanind, chan in enumerate(channels):
                waveforms[chanind].append(elements[pos-1][chan][0])
                m1s[chanind].append(elements[pos-1][chan][1])
                m2s[chanind].append(elements[pos-1][chan][2])
                nreps.append(self._sequencing[pos][1])
                trig_waits.append(self._sequencing[pos][0])
                jump_tos.append(self._sequencing[pos][2])
                goto_states.append(self._sequencing[pos][3])

        return (waveforms, m1s, m2s, nreps, trig_waits, goto_states,
                jump_tos, list(channels))


def _subelementBuilder(blueprint, SR, durations):
    """
    The function building a blueprint, returning a numpy array.

    This is a single-blueprint forger. Multiple blueprints are forged with
    elementBuilder.
    """

    # Important: building the element must NOT modify the bluePrint, therefore
    # all lists are copied
    funlist = blueprint._funlist.copy()
    argslist = blueprint._argslist.copy()
    namelist = blueprint._namelist.copy()
    tslist = blueprint._tslist.copy()
    marker1 = blueprint.marker1.copy()
    marker2 = blueprint.marker2.copy()
    segmark1 = blueprint._segmark1.copy()
    segmark2 = blueprint._segmark2.copy()

    no_of_waits = funlist.count('waituntil')

    if sum(tslist) != len(durations)+no_of_waits:
        print('-'*45)
        print(tslist, durations, no_of_waits)

        raise ValueError('The specified timesteps do not match the number ' +
                         'of durations. ({} and {})'.format(sum(tslist),
                                                            len(durations) +
                                                            no_of_waits))

    # handle waituntil by translating it into a normal function
    waitpositions = [ii for ii, el in enumerate(funlist) if el == 'waituntil']
    for nw in range(no_of_waits):
        pos = waitpositions[nw]
        funlist[pos] = PulseAtoms.waituntil
        elapsed_time = sum(durations[:pos])
        wait_time = argslist[pos][0]
        dur = wait_time - elapsed_time
        if dur < 0:
            raise ValueError('Inconsistent timing. Can not wait until ' +
                             '{} at position {}.'.format(wait_time, pos) +
                             ' {} elapsed already'.format(elapsed_time))
        else:
            durations.insert(pos, dur)

    # update the durations to accomodate for some segments having
    # timesteps larger than 1
    newdurations = []
    steps = [0] + list(np.cumsum(blueprint._tslist))
    for ii in range(len(steps)-1):
        dur = sum(durations[steps[ii]:steps[ii+1]])
        newdurations.append(dur)

    # The actual forging of the waveform
    parts = [ft.partial(fun, *args) for (fun, args) in zip(funlist, argslist)]
    blocks = [list(p(SR, d)) for (p, d) in zip(parts, newdurations)]
    output = [block for sl in blocks for block in sl]

    # now make the markers
    time = np.linspace(0, sum(newdurations), sum(newdurations)*SR)  # round off
    m1 = np.zeros_like(time)
    m2 = m1.copy()
    dt = time[1] - time[0]
    # update the 'absolute time' marker list with 'relative time'
    # (segment bound) markers converted to absolute time
    elapsed_times = np.cumsum([0] + newdurations)
    for pos, spec in enumerate(segmark1):
        if spec[1] is not 0:
            ontime = elapsed_times[pos] + spec[0]  # spec is (delay, duration)
            marker1.append((ontime, spec[1]))
    for pos, spec in enumerate(segmark2):
        if spec[1] is not 0:
            ontime = elapsed_times[pos] + spec[0]  # spec is (delay, duration)
            marker2.append((ontime, spec[1]))
    msettings = [marker1, marker2]
    marks = [m1, m2]
    for marker, setting in zip(marks, msettings):
        for (t, dur) in setting:
            ind = np.abs(time-t).argmin()
            chunk = int(np.round(dur/dt))
            marker[ind:ind+chunk] = 1

    return np.array([output, m1, m2, time]), newdurations


def elementBuilder(blueprints, SR, durations, channels=None,
                   returnnewdurs=False):
    """
    Forge blueprints into an element

    Args:
        blueprints (Union[BluePrint, list]): A single blueprint or a list of
            blueprints.
        SR (int): The sample rate (Sa/s)
        durations (list): List of durations or a list of lists of durations
            if different blueprints have different durations. If a single list
            is given, this list is used for all blueprints.
        channels (Union[list, None]): A list specifying the channels of the
            blueprints in the list. If None, channels 1, 2, .. are assigned
        returnnewdurs (bool): If True, the returned dictionary contains the
            newdurations.

    Returns:
        dict: Dictionary with channel numbers (ints) as keys and forged
            blueprints as values. A forged blueprint is a numpy array
            given by np.array([wfm, m1, m2, time]). If returnnewdurs is True,
            a list of [wfm, m1, m2, time, newdurs] is returned instead.

    Raises:
        ValueError: if blueprints does not contain BluePrints
        ValueError: if the wrong number of blueprints/durations is given
    """

    # Validation
    if not (isinstance(blueprints, BluePrint) or isinstance(blueprints, list)):
        raise ValueError('blueprints must be a BluePrint object or a list of '
                         'BluePrint objects. '
                         'Received {}.'.format(type(blueprints)))
    if isinstance(blueprints, BluePrint):
        blueprints = [blueprints]
    # Allow for using a single durations list for all blueprints
    if not isinstance(durations[0], list):
        durations = [durations]*len(blueprints)

    if channels is None:
        channels = [ii for ii in range(len(blueprints))]

    bpdurs = zip(blueprints, durations)
    if not returnnewdurs:
        subelems = [_subelementBuilder(bp, SR, dur)[0] for (bp, dur) in bpdurs]
    else:
        subelems = []
        for (bp, dur) in bpdurs:
            subelems.append(list(_subelementBuilder(bp, SR, dur)[0]) +
                            [_subelementBuilder(bp, SR, dur)[1]])

    outdict = dict(zip(channels, subelems))

    return outdict


def bluePrintPlotter(blueprints, SR, durations, fig=None, axs=None):
    """
    Plots a bluePrint or list of blueprints for easy overview.

    Args:
        blueprints (Union[BluePrint, list]): A single BluePrint or a
            list of blueprints to plot.
        SR (int): The sample rate (Sa/s)
        durations (list): Either a list of durations or a list of lists
            of durations in case the blueprints have different durations.
            If only a single list of durations is given, this list is used
            for all blueprints.
        fig (Union[matplotlib.figure.Figure, None]): The figure on which to
            plot. If None is given, a new instance is created.
        axs (Union[list, None]): A list of
            matplotlib.axes._subplots.AxesSubplot to plot onto. If None is
            given, a new list is created.

    TODO: all sorts of validation on lengths of blueprint and the like
    """
    # Allow single blueprint
    if not isinstance(blueprints, list):
        blueprints = [blueprints]
    # Allow a single durations list for all blueprint
    if not isinstance(durations[0], list):
        durations = [durations]*len(blueprints)

    # Validation
    if not len(durations) == len(blueprints):
        raise ValueError('Number of specified blueprints does not match '
                         'number of specified (sets of) durations '
                         '({} and {})'.format(len(blueprints),
                                              len(durations)))

    if fig is None:
        fig = plt.figure()
    N = len(blueprints)

    if axs is None:
        axs = [fig.add_subplot(N, 1, ii+1) for ii in range(N)]

    for ii in range(N):
        ax = axs[ii]
        arrays, newdurs = _subelementBuilder(blueprints[ii], SR, durations[ii])
        wfm = arrays[0, :]
        m1 = arrays[1, :]
        m2 = arrays[2, :]
        yrange = wfm.max() - wfm.min()
        ax.set_ylim([wfm.min()-0.05*yrange, wfm.max()+0.2*yrange])
        time = np.linspace(0, np.sum(newdurs), np.sum(newdurs)*SR)

        # plot lines indicating the durations
        for dur in np.cumsum(newdurs):
            ax.plot([dur, dur], [ax.get_ylim()[0],
                                 ax.get_ylim()[1]],
                    color=(0.312, 0.2, 0.33),
                    alpha=0.3)

        # plot the waveform
        ax.plot(time, wfm, lw=3, color=(0.6, 0.4, 0.3), alpha=0.4)

        # plot the markers
        y_m1 = wfm.max()+0.15*yrange
        marker_on = np.ones_like(m1)
        marker_on[m1 == 0] = np.nan
        marker_off = np.ones_like(m1)
        ax.plot(time, y_m1*marker_off, color=(0.6, 0.1, 0.1), alpha=0.2, lw=2)
        ax.plot(time, y_m1*marker_on, color=(0.6, 0.1, 0.1), alpha=0.6, lw=2)
        #
        y_m2 = wfm.max()+0.10*yrange
        marker_on = np.ones_like(m2)
        marker_on[m2 == 0] = np.nan
        marker_off = np.ones_like(m2)
        ax.plot(time, y_m2*marker_off, color=(0.1, 0.1, 0.6), alpha=0.2, lw=2)
        ax.plot(time, y_m2*marker_on, color=(0.1, 0.1, 0.6), alpha=0.6, lw=2)

    # Prettify a bit
    for ax in axs[:-1]:
        ax.set_xticks([])
    axs[-1].set_xlabel('Time (s)')
    for ax in axs:
        yt = ax.get_yticks()
        ax.set_yticks(yt[2:-2])
        ax.set_ylabel('Signal (V)')
    fig.subplots_adjust(hspace=0)
