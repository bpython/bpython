import unittest
from itertools import islice

from bpython import repl


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.history = repl.History('#%d' % x for x in range(1000))

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

        self.assertEqual(self.history.back(), '#999')
        self.assertEqual(self.history.forward(), '#lastnumber!')

    def test_reset(self):
        self.history.enter('#lastnumber!')
        self.history.reset()

        self.assertEqual(self.history.back(), '#999')
        self.assertEqual(self.history.forward(), '')


class TestMatchesIterator(unittest.TestCase):

    def setUp(self):
        self.matches = ['bobby', 'bobbies', 'bobberina']
        self.matches_iterator = repl.MatchesIterator(current_word='bob',
                                                     matches=self.matches)

    def test_next(self):
        self.assertEqual(self.matches_iterator.next(), self.matches[0])

        for x in range(len(self.matches) - 1):
            self.matches_iterator.next()

        self.assertEqual(self.matches_iterator.next(), self.matches[0])
        self.assertEqual(self.matches_iterator.next(), self. matches[1])
        self.assertNotEqual(self.matches_iterator.next(), self.matches[1])

    def test_previous(self):
        self.assertEqual(self.matches_iterator.previous(), self.matches[2])

        for x in range(len(self.matches) - 1):
            self.matches_iterator.previous()

        self.assertNotEqual(self.matches_iterator.previous(), self.matches[0])
        self.assertEqual(self.matches_iterator.previous(), self.matches[1])
        self.assertEqual(self.matches_iterator.previous(), self.matches[0])

    def test_nonzero(self):
        """self.matches_iterator should be False at start,
        then True once we active a match.
        """
        self.assertFalse(self.matches_iterator)
        self.matches_iterator.next()
        self.assertTrue(self.matches_iterator)

    def test_iter(self):
        slice = islice(self.matches_iterator, 0, 9)
        self.assertEqual(list(slice), self.matches * 3)

    def test_current(self):
        self.assertRaises(ValueError, self.matches_iterator.current)
        self.matches_iterator.next()
        self.assertEqual(self.matches_iterator.current(), self.matches[0])

    def test_update(self):
        slice = islice(self.matches_iterator, 0, 3)
        self.assertEqual(list(slice), self.matches)

        newmatches = ['string', 'str', 'set']
        self.matches_iterator.update('s', newmatches)

        newslice = islice(newmatches, 0, 3)
        self.assertNotEqual(list(slice), self.matches)
        self.assertEqual(list(newslice), newmatches)

from bpython.args import parse

class TestRepl(unittest.TestCase):

    def setUp(self):
        config = parse(args=[])[0]
        self.interp = repl.Interpreter()
        self.repl = repl.Repl(self.interp, config)

    def test_attr_matches(self):
        # test with builtin object
        self.assertEqual(self.repl.attr_matches('str.s'),
                         ['str.%s' % x for x in dir(str) if x.startswith('s')])
        self.assertEqual(self.repl.attr_matches('int.de'),
                         ['int.%s' % x for x in dir(int) if x.startswith('de')])
        self.assertEqual(self.repl.attr_matches('tuple.foospamegg'), [])

        # test with a new object
        class A(object):
            spam = 'egg'

            @property
            def clone(self):
                return A()
        self.interp.locals['A'] = A

        self.assertEqual(self.repl.attr_matches('A.spam'), ['A.spam'])
        # test nested attributes
        self.assertEqual(self.repl.attr_matches('A.spam.isdi'),
                         ['A.spam.isdigit'])
        self.assertEqual(self.repl.attr_matches('A.clone.s'), ['A.clone.spam'])



if __name__ == '__main__':
    unittest.main()
