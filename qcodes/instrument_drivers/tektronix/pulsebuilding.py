# implementing what Filip asked for...
#
# Terminology:
# Segments are collected in a blueprint. One or more blueprints are forged
# into an element.
#
# In this iteration, we do it in a horribly object-oriented way

from collections import OrderedDict
from inspect import signature
import functools as ft
import numpy as np
import matplotlib.pyplot as plt
plt.ion()

# "global" variable, the sample rate
# TODO: figure out where to get this from (obviously the AWG SR, but how?)
SR = 100


class PulseAtoms:
    """
    A class full of static methods.
    The basic pulse shapes.

    Any pulse shape function must return a list and have duration as its
    final argument.
    """

    @staticmethod
    def sine(freq, ampl, off, dur):
        time = np.linspace(0, dur, dur*SR)

        return list(ampl*np.sin(freq*time)+off)

    @staticmethod
    def ramp(slope, dur):
        time = np.linspace(0, dur, dur*SR)

        return list(slope*time)

    @staticmethod
    def waituntil(dur):
        return list(np.zeros(dur*SR))


class BluePrint():
    """
    The class to contain the bluePrint of an element.

    Several bluePrints may be passed to the elementBuilder, which turns
    them into numpy arrays.
    """

    def __init__(self, funlist, argslist, namelist, tslist=None):
        """
        TO-DO: (probably) change the call signature ot take in single
        segments and not the full lists.

        Args:
            funlist (list): List of functions
            argslist (list): List of tuples of arguments
            namelist (list): List of names for the functions
            tslist (list): List of timesteps for each segment
        """

        # TO-DO: infer names from signature if not given

        namelist = self._make_names_unique(namelist)

        self._funlist = funlist
        self._argslist = argslist
        self._namelist = namelist
        if tslist is None:
            self._tslist = [1]*len(namelist)

        self._bp = OrderedDict()
        for (name, fun, args) in zip(namelist, funlist, argslist):
            # Allow users to input incorrect arg tuples, like (3)
            try:
                len(args)
            except TypeError:
                args = (args,)
            self._bp.update({name: {'function': fun, 'args': args,
                                    'timesteps': 1}})

    def _updatelists(self):
        self._funlist = []
        self._argslist = []
        self._namelist = []
        self._tslist = []
        for (key, val) in self._bp.items():
            self._namelist.append(key)
            self._funlist.append(val['function'])
            self._argslist.append(val['args'])
            self._tslist.append(val['timesteps'])

    @staticmethod
    def _make_names_unique(lst):
        """
        Make all strings in the input list unique
        by appending numbers to reoccuring strings

        Args:
            lst (list): List of strings. Intended for the _namelist

        """
        lst.reverse()
        for el in lst:
            if lst.count(el) > 1:
                for ii in range(lst.count(el), 1, -1):
                    # TODO: what is the appropriate formatter here?
                    lst[lst.index(el)] += '{}'.format(ii)
        lst.reverse()
        return lst

    def showPrint(self):
        """
        Pretty-print the contents of the BluePrint.
        """
        lzip = zip(self._namelist, self._funlist, self._argslist)
        for ind, (name, fun, args) in enumerate(lzip):
            print('Segment {}: {}, {}, {}'.format(ind+1, name, fun, args))

    def changeArg(self, name, arg, value):
        """
        Change an argument of one of the functions in the blueprint.
        The input argument may be a string (the name of the argument)
        or an int specifying the arg's position.
        """
        # TODO: is there any reason to use tuples internally?
        # TODO: add input validation

        if isinstance(arg, str):
            sig = signature(self._bp[name]['function'])
            for ii, param in enumerate(sig.parameters):
                if arg == param:
                    arg = ii
                    break

        # Mutating the immutable...
        larg = list(self._bp[name]['args'])
        larg[arg] = value
        self._bp[name]['args'] = tuple(larg)
        self._updatelists()

    def changeDuration(self, name, n):
        """
        Change the duration (in number of timesteps) of the blueprint segment
        with the specified name.

        Args:
            name (str): The name of a segment of the blueprint.
            n (int): The number of timesteps for this segment to last.
        """
        n_is_whole_number = float(n).is_integer()
        if not (n >= 1 and n_is_whole_number):
            raise ValueError('n must be a whole number strictly' +
                             ' greater than 0.')

        self._bp[name]['timesteps'] = n
        self._updatelists()

    def copy(self):
        fl = []
        nl = []
        al = []
        for name in self._bp:
            fl.append(self._bp[name]['function'])
            al.append(self._bp[name]['args'])
            nl.append(name)
        return BluePrint(fl, al, nl)

    def removeSegment(self, name):
        """
        Remove the specified segment from the blueprint.

        Args:
            name (str): The name of the segment to remove.
        """
        self._bp.pop(name)
        self._updatelists()

    def __add__(self, other):
        """
        Add two BluePrints. The second argument is appended to the first
        and a new BluePrint is returned.
        """
        if not isinstance(other, BluePrint):
            raise ValueError("""
                             BluePrint can only be added to another Blueprint.
                             Received an object of type {}
                             """.format(type(other)))

        nl = self._namelist + other._namelist
        al = self._argslist + other._argslist
        fl = self._funlist + self._funlist

        return BluePrint(fl, al, nl)


def elementBuilder(blueprint, durations):
    """
    The function building a blueprint, returning a numpy array.

    TO-DO: add proper behaviour for META functions like 'wait until X'
    TO-DO: add support for multiple blueprints
    """

    # update the durations to accomodate for some segments having
    # timesteps larger than 1
    newdurations = []
    steps = [0] + list(np.cumsum(blueprint._tslist))
    for ii in range(len(steps)-1):
        dur = sum(durations[steps[ii]:steps[ii+1]])
        newdurations.append(dur)

    funlist = blueprint._funlist
    argslist = blueprint._argslist
    parts = [ft.partial(fun, *args) for (fun, args) in zip(funlist, argslist)]
    blocks = [p(d) for (p, d) in zip(parts, newdurations)]
    output = [block for sl in blocks for block in sl]
    return np.array(output)


def bluePrintPlotter(blueprints, durations):
    """
    Plots a bluePrint or list of blueprints for easy overview.

    TODO: all sorts of validation on lengths of blueprint and the like
    """
    if not isinstance(blueprints, list):
        blueprints = [blueprints]

    fig = plt.figure()
    N = len(blueprints)
    time = np.linspace(0, np.sum(durations), np.sum(durations)*SR)
    for ii in range(N):
        ax = fig.add_subplot(N, 1, ii+1)
        wfm = elementBuilder(blueprints[ii], durations)
        for dur in np.cumsum(durations):
            ax.plot([dur, dur], [wfm.min(), wfm.max()],
                    color=(0.312, 0.2, 0.33),
                    alpha=0.3)
        ax.plot(time, wfm, lw=2, color=(0.6, 0.3, 0.3), alpha=0.4)


if __name__ == '__main__':

    ramp = PulseAtoms.ramp
    sine = PulseAtoms.sine

    durations = [1, 2, 0.8]

    bp1 = BluePrint([ramp, sine, ramp],
                    [(-1,), (40, 1, 1), (2,)],
                    ['down', 'wiggle', 'up'])

    elem1 = elementBuilder(bp1, durations)
    bp2 = bp1.copy()
    bp2.changeArg('wiggle', 'freq', 20)
    elem2 = elementBuilder(bp2, durations)
    bp3 = bp1 + bp2
    bp3.removeSegment('up2')
    bp3.changeDuration('wiggle', 2)

    bluePrintPlotter([bp1, bp2], durations)
    bluePrintPlotter(bp3, durations+durations)
