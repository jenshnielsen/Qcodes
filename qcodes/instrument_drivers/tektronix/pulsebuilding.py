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

    Any pulse shape function must return a list and have SR, duration as its
    final two arguments.
    """

    @staticmethod
    def sine(freq, ampl, off, SR, dur):
        time = np.linspace(0, dur, dur*SR)
        freq *= 2*np.pi
        return list(ampl*np.sin(freq*time)+off)

    @staticmethod
    def ramp(slope, offset, SR, dur):
        time = np.linspace(0, dur, dur*SR)
        return list(slope*time+offset)

    @staticmethod
    def waituntil(dummy, SR, dur):
        # for internal call signature consistency, a dummy variable is needed
        return list(np.zeros(dur*SR))

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
        TO-DO: (probably) change the call signature ot take in single
        segments and not the full lists.

        Args:
            funlist (list): List of functions
            argslist (list): List of tuples of arguments
            namelist (list): List of names for the functions
            tslist (list): List of timesteps for each segment
            marker1 (list): List of marker1 specification tuples
            marker2 (list): List of marker2 specifiation tuples
        """
        # TODO: validate input

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
        lst = [letter for letter in string if not letter.isdigit()]
        return ''.join(lst)

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
        markerselect[markerID][position] = specs

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
        return BluePrint(self._funlist.copy(),
                         self._argslist.copy(),
                         self._namelist.copy(),
                         self._tslist.copy(),
                         self.marker1.copy(),
                         self.marker2.copy())

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

        nl = self._namelist + other._namelist
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
        Set all (subelements) on the specified channel to be variations of
        a basic blueprint. Note: this overwrites everything on that channel.

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

    def plotSequence(self):
        """
        Visualise the sequence
        """
        if not self.checkConsistency():
            raise ValueError('Can not plot sequence: Something is '
                             'inconsistent. Please run '
                             'checkConsistency(verbose=True) for more details')

        fig = plt.figure()

        # Now get the dimensions. Since the check passed, we may be slobby
        chans = set([tup[0] for tup in self._data.keys()])
        seqlen = len([t for t in self._data.keys() if t[0] == list(chans)[0]])

        # loop through the sequence
        # TODO: major indexing problems
        for seqel in range(1, seqlen+1):
            axs = []
            bps = []
            for ii, chan in enumerate(chans):
                axs.append(fig.add_subplot(len(chans), seqlen,
                                           ii*seqlen+seqel))
                bps.append(self._data[(chan, seqel)][0])
            durations = self._data[(chan, seqel)][1]  # all durations the same
            bluePrintPlotter(bps, self._awgspecs['SR'], durations, fig, axs)
            # aesthetics
            for ax in axs[:-1]:
                ax.set_xticks([])
            # If sequencing settings are set, print them on the plot
            try:
                seqinfo = self._sequencing[seqel]
                axs[0].set_title('w:{}, reps:{}, jump:{}, goto:{}'.format(*seqinfo))
            except KeyError:
                pass
        # aesthetics
        fig.subplots_adjust(hspace=0)


def _subelementBuilder(blueprint, SR, durations):
    """
    The function building a blueprint, returning a numpy array.

    This is a single-blueprint forger. It should be easy to stack several.

    TO-DO: add proper behaviour for META functions like 'wait until X'
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
    blocks = [p(SR, d) for (p, d) in zip(parts, newdurations)]
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

    return np.array([output, m1, m2]), newdurations


def elementBuilder(blueprints, SR, durations, channels=None):
    """
    Forge blueprints into an element

    Args:
        blueprints (Union[BluePrint, list]): A single blueprint or a list of
            blueprints.
        SR (int): The sample rate (Sa/s)
        durations (list): List of durations
        channels (Union[list, None]): A list specifying the channels of the
            blueprints in the list. If None, channels 1, 2, .. are assigned

    Returns:
        dict: Dictionary with channel numbers (ints) as keys and forged
            blueprints as values. A forged blueprint is a numpy array
            given by np.array([wfm, m1, m2]).
    """

    # Validation
    if not (isinstance(blueprints, BluePrint) or isinstance(blueprints, list)):
        raise ValueError('blueprints must be a BluePrint object or a list of '
                         'BluePrint objects. '
                         'Received {}.'.format(type(blueprints)))
    if isinstance(blueprints, BluePrint):
        blueprints = [blueprints]

    if channels is None:
        channels = [ii for ii in range(len(blueprints))]

    subelems = [_subelementBuilder(bp, SR, durations)[0] for bp in blueprints]
    outdict = dict(zip(channels, subelems))

    return outdict


def bluePrintPlotter(blueprints, SR, durations, fig=None, axs=None):
    """
    Plots a bluePrint or list of blueprints for easy overview.

    TODO: all sorts of validation on lengths of blueprint and the like
    """
    if not isinstance(blueprints, list):
        blueprints = [blueprints]

    if fig is None:
        fig = plt.figure()
    N = len(blueprints)

    for ii in range(N):
        if axs is None:
            ax = fig.add_subplot(N, 1, ii+1)
        else:
            ax = axs[ii]
        arrays, newdurs = _subelementBuilder(blueprints[ii], SR, durations)
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
