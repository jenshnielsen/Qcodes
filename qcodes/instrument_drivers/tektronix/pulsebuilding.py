# implementing what Filip asked for...
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
        pass


class BluePrint():
    """
    The class to contain the bluePrint of an element.

    Several bluePrints may be passed to the elementBuilder, which turns
    them into numpy arrays.
    """

    def __init__(self, funlist, argslist, namelist):
        """
        Args:
            funlist (list): List of functions
            argslist (list): List of tuples of arguments
            namelist (list): List of names for the functions
        """
        self._funlist = funlist
        self._argslist = argslist

        self._bp = OrderedDict()
        for (name, fun, args) in zip(namelist, funlist, argslist):
            # Allow users to input incorrect arg tuples, like (3)
            try:
                len(args)
            except TypeError:
                args = (args,)
            self._bp.update({name: {'function': fun, 'args': args}})

    def _updatelists(self):
        self._funlist = []
        self._argslist = []
        for val in self._bp.values():
            self._funlist.append(val['function'])
            self._argslist.append(val['args'])

    def showPrint(self):
        """
        Pretty-print the contents of the BluePrint.
        """
        pass

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

    def copy(self):
        fl = []
        nl = []
        al = []
        for name in self._bp:
            fl.append(self._bp[name]['function'])
            al.append(self._bp[name]['args'])
            nl.append(name)
        return BluePrint(fl, al, nl)


def elementBuilder(blueprint, durations):
    """
    The function building a blueprint, returning a numpy array.

    TO-DO: add proper behaviour for META functions like 'wait until X'
    TO-DO: add support for multiple blueprints
    """

    funlist = blueprint._funlist
    argslist = blueprint._argslist
    parts = [ft.partial(fun, *args) for (fun, args) in zip(funlist, argslist)]
    blocks = [p(d) for (p, d) in zip(parts, durations)]
    output = [block for sl in blocks for block in sl]
    return output


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

    fig1 = plt.figure()
    ax1 = fig1.add_subplot(121)
    ax2 = fig1.add_subplot(122)
    ax1.plot(elem1)
    ax2.plot(elem2)
