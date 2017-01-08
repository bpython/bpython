# encoding: utf-8

from six.moves import range

from bpython.history import History
from bpython.test import unittest


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.history = History('#%d' % x for x in range(1000))

    def test_is_at_start(self):
        self.history.first()

        self.assertNotEqual(self.history.index, 0)
        self.assertTrue(self.history.is_at_end)
        self.history.forward()
        self.assertFalse(self.history.is_at_end)

    def test_is_at_end(self):
        self.history.last()

        self.assertEqual(self.history.index, 0)
        self.assertTrue(self.history.is_at_start)
        self.assertFalse(self.history.is_at_end)

    def test_first(self):
        self.history.first()

        self.assertFalse(self.history.is_at_start)
        self.assertTrue(self.history.is_at_end)

    def test_last(self):
        self.history.last()

        self.assertTrue(self.history.is_at_start)
        self.assertFalse(self.history.is_at_end)

    def test_back(self):
        self.assertEqual(self.history.back(), '#999')
        self.assertNotEqual(self.history.back(), '#999')
        self.assertEqual(self.history.back(), '#997')
        for x in range(997):
            self.history.back()
        self.assertEqual(self.history.back(), '#0')

    def test_forward(self):
        self.history.first()

        self.assertEqual(self.history.forward(), '#1')
        self.assertNotEqual(self.history.forward(), '#1')
        self.assertEqual(self.history.forward(), '#3')
        #  1000 == entries   4 == len(range(1, 3) ===> '#1000' (so +1)
        for x in range(1000 - 4 - 1):
            self.history.forward()
        self.assertEqual(self.history.forward(), '#999')

    def test_append(self):
        self.history.append('print "foo\n"\n')
        self.history.append('\n')

        self.assertEqual(self.history.back(), 'print "foo\n"')

    def test_enter(self):
        self.history.enter('#lastnumber!')

        self.assertEqual(self.history.back(), '#lastnumber!')
        self.assertEqual(self.history.forward(), '#lastnumber!')

    def test_enter_2(self):
        self.history.enter('#50')

        self.assertEqual(self.history.back(), '#509')
        self.assertEqual(self.history.back(), '#508')
        self.assertEqual(self.history.forward(), '#509')

    def test_reset(self):
        self.history.enter('#lastnumber!')
        self.history.reset()

        self.assertEqual(self.history.back(), '#999')
        self.assertEqual(self.history.forward(), '')
