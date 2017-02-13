# implementing what Filip asked for...
#
# Terminology:
# Segments are collected in a blueprint. One or more blueprints are forged
# into an element.
#
# In this iteration, we do it in a horribly object-oriented way

from inspect import signature
import functools as ft
import numpy as np

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

    @staticmethod
    def gaussian(ampl, sigma, mu, offset, dur):
        """
        Returns a Gaussian of integral ampl (when offset==0)
        """
        time = np.linspace(0, dur, dur*SR)
        baregauss = np.exp((-(time-mu)**2/(2*sigma**2)))
        normalisation = 1/np.sqrt(2*sigma**2*np.pi)
        return ampl*baregauss*normalisation


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

        # Infer names from signature if not given, i.e. allow for '' names
        for ii, name in enumerate(namelist):
            if name == '':
                namelist[ii] = funlist[ii].__name__

        self._funlist = funlist
        self._argslist = argslist
        self._namelist = namelist
        namelist = self._make_names_unique(namelist)

        if tslist is None:
            self._tslist = [1]*len(namelist)
        else:
            self._tslist = tslist

    @staticmethod
    def _basename(string):
        """
        Remove trailing numbers from a string.
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

        # baselst.reverse()
        # lst.reverse()
        # for el in lst:
        #     baseel = BluePrint._basename(el)
        #     if baselst.count(baseel) > 1:
        #         print('Found {} more than once'.format(el))
        #         for ii in range(baselst.count(baseel), 1, -1):
        #             print(lst, el)
        #             # TODO: what is the appropriate formatter here?
        #             lst[lst.index(el)] = '{}{}'.format(baseel, ii)
        # lst.reverse()
        # return lst

    def showPrint(self):
        """
        Pretty-print the contents of the BluePrint.
        """
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

            # allow the user to input single values instead of (val,)
            no_of_args = len(self._argslist[position])
            if not isinstance(value, tuple) and no_of_args == 1:
                value = (value,)

            if isinstance(arg, str):
                sig = signature(self._funlist[position])
                for ii, param in enumerate(sig.parameters):
                    if arg == param:
                        arg = ii
                        break

            # Mutating the immutable...
            larg = list(self._argslist[position])
            larg[arg] = value
            self._argslist[position] = tuple(larg)

    def changeDuration(self, name, n):
        """
        Change the duration (in number of timesteps) of the blueprint segment
        with the specified name.

        Args:
            name (str): The name of a segment of the blueprint.
            n (int): The number of timesteps for this segment to last.
        """

        position = self._namelist.index(name)

        n_is_whole_number = float(n).is_integer()
        if not (n >= 1 and n_is_whole_number):
            raise ValueError('n must be a whole number strictly' +
                             ' greater than 0.')

        self._tslist[position] = n

    def copy(self):
        return BluePrint(self._funlist.copy(),
                         self._argslist.copy(),
                         self._namelist.copy(),
                         self._tslist.copy())

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
        else:
            self._namelist.insert(pos, name)
            self._namelist = self._make_names_unique(self._namelist)
            self._funlist.insert(pos, func)
            self._argslist.insert(pos, args)
            self._tslist.insert(pos, ts)

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
        fl = self._funlist + self._funlist

        return BluePrint(fl, al, nl)

    def __eq__(self, other):
        """
        Compare two blueprints. They are the same iff all four
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
        return True

# testing another call signature for __init__


class BluePrint_alt(BluePrint):
    """
    test class for testing an alternative call signature for __init__.
    """
    pass


def elementBuilder(blueprint, durations):
    """
    The function building a blueprint, returning a numpy array.

    This is a single-blueprint forger. It should be easy to stack several.

    TO-DO: add proper behaviour for META functions like 'wait until X'
    """

    funlist = blueprint._funlist
    argslist = blueprint._argslist
    namelist = blueprint._namelist
    tslist = blueprint._tslist

    #TODO: make 'waituntil' not break this validation
    if sum(tslist) != len(durations):
        raise ValueError('The specified timesteps do not match the number ' +
                         'of durations. ({} and {})'.format(sum(tslist),
                                                            len(durations)))

    # Take care of 'meta'-function inputs before proceeding
    # all 'actions' return the same things; new lists

    def waituntilaction(durations, funlist, n, tau):
        timesofar = sum(durations[:n])
        if tau-timesofar < 0:
            raise ValueError("""
                             Inconsistent duration specifications.
                             Can not wait until {} s at segment {}, since
                             the waveform is already {} s long at this point.
                             """.format(tau, n, timesofar))

        funlist.insert(n, PulseAtoms.waituntil)  # if meta func lives in names
        # funlist[n] = PulseAtoms.waituntil  # if meta func lives in funcs
        durations.insert(n, tau-timesofar)

        return durations, funlist

    metaactions = {'waituntil': waituntilaction}

    # TODO: perhaps meta functions should live in funlist, not namelist?
    for name in namelist:
        if name in metaactions:
            (durations, funlist) = metaactions[name]  # where are tau and n?

    # update the durations to accomodate for some segments having
    # timesteps larger than 1
    newdurations = []
    steps = [0] + list(np.cumsum(blueprint._tslist))
    for ii in range(len(steps)-1):
        dur = sum(durations[steps[ii]:steps[ii+1]])
        newdurations.append(dur)

    # The actual forging
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
