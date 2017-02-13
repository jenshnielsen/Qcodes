from unittest import TestCase
import unittest as ut

from qcodes.instrument_drivers.tektronix import pulsebuilding as pb

sine = pb.PulseAtoms.sine
ramp = pb.PulseAtoms.ramp


class TestStaticMethods(TestCase):

    def test_name_uniquiefier(self):
        inp = ['aa', 'aa', 'bb', 'bb', 'aa', 'ac']
        outp = ['aa', 'aa2', 'bb', 'bb2', 'aa3', 'ac']

        self.assertEqual(pb.BluePrint._make_names_unique(inp), outp)

        inp = ['a', 'aa', 'aaa', 'aa']
        outp = ['a', 'aa', 'aaa', 'aa2']

        self.assertEqual(pb.BluePrint._make_names_unique(inp), outp)


class TestInsertions(TestCase):

    def setUp(self):

        self.blueprint = pb.BluePrint([ramp, sine, ramp, sine],
                                      [(0,), (20, 1, 1), (0,), (10, 2, 2)],
                                      ['', 'wiggle', '', ''])

    def test_equality(self):

        testbp_wrongname = pb.BluePrint([ramp, sine, ramp, sine],
                                        [(0,), (20, 1, 1), (0,), (10, 2, 2)],
                                        ['', 'wiggl', '', ''])

        testbp_wrongarg = pb.BluePrint([ramp, sine, ramp, sine],
                                       [(0,), (20, 1, 2), (0,), (10, 2, 2)],
                                       ['', 'wiggle', '', ''])

        testbp_wrongts = pb.BluePrint([ramp, sine, ramp, sine],
                                      [(0,), (20, 1, 1), (0,), (10, 2, 2)],
                                      ['', 'wiggle', '', ''],
                                      [1, 1, 1, 2])

        self.assertNotEqual(testbp_wrongarg, self.blueprint)
        self.assertEqual(testbp_wrongname, self.blueprint)
        self.assertNotEqual(testbp_wrongts, self.blueprint)

    def test_insertion_of_segment(self):

        testbp = pb.BluePrint([], [], [])
        testbp.insertSegment(0, ramp, 0)
        testbp.insertSegment(1, sine, (20, 1, 1), 'wiggle')
        testbp.insertSegment(2, ramp, 0)
        testbp.insertSegment(3, sine, (10, 2, 2))

        self.assertEqual(testbp, self.blueprint)

    def test_copying(self):

        testbp = self.blueprint.copy()
        self.assertEqual(testbp, self.blueprint)


if __name__ == '__main__':
    ut.main()
