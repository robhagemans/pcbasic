"""
PC-BASIC tests.test_pickle
Test pickling various kinds of objects

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import pickle
from io import open

from pcbasic import Session
from pcbasic.basic.base.codestream import TokenisedStream
from pcbasic.basic.base.error import Exit

from tests.unit.utils import TestCase, run_tests


class PickleTest(TestCase):
    """Test pickling various kinds of objects."""

    tag = u'pickle'

    def test_pickle_tokenisedstream(self):
        """Pickle TokenisedStream object."""
        ts = TokenisedStream()
        ts.write(b'123')
        ts.seek(0)
        ts.seek(0)
        ps = pickle.dumps(ts)
        ts2 = pickle.loads(ps)
        assert ts2.read() == b'123'

    def test_pickle_session(self):
        """Pickle Session object."""
        with Session() as s:
            s.execute('a=1')
        ps = pickle.dumps(s)
        s2 = pickle.loads(ps)
        assert s2.get_variable('a!') == 1

    def test_pickle_session_open_file(self):
        """Pickle Session object with open file."""
        s = Session(devices={'a': self.output_path()})
        s.execute('open "A:TEST" for output as 1')
        ps = pickle.dumps(s)
        s2 = pickle.loads(ps)
        s2.execute('print#1, "test"')
        s2.close()
        with open(self.output_path('TEST')) as f:
            assert f.read() == u'test\n\x1a'

    def test_pickle_session_running(self):
        """Pickle Session object with running program."""
        s = Session()
        s.execute('10 for i%=1 to 10: system: next')
        try:
            s.execute('run')
        except Exit:
            pass
        ps = pickle.dumps(s)
        s2 = pickle.loads(ps)
        # resume the running program
        try:
            s2.interact()
        except Exit:
            pass
        assert s2.get_variable('i%') == 2


if __name__ == '__main__':
    run_tests()
