"""
PC-BASIC test.cassette
Tests for cassette device

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import shutil

from pcbasic import Session
from tests.unit.utils import TestCase, run_tests


HERE = os.path.dirname(os.path.abspath(__file__))


def _input_file(name):
    """Test input file."""
    return os.path.join(HERE, 'input', 'cassette', name)

def _output_file(name):
    """Test output file."""
    return os.path.join(HERE, 'output', 'cassette', name)


class CassetteTest(TestCase):
    """Cassette tests."""

    tag = u'cassette'

    def setUp(self):
        """Ensure output directory exists."""
        try:
            os.makedirs(_output_file(u''))
        except EnvironmentError:
            pass

    def test_cas_load(self):
        """Load from a CAS file."""
        with Session(devices={b'CAS1:': _input_file('test.cas')}) as s:
            s.execute('load "cas1:test"')
            s.execute('list')
            output = [_row.strip() for _row in self.get_text(s)]
        assert output[:4] == [
            b'not this.B Skipped.',
            b'test    .B Found.',
            b'10 OPEN "output.txt" FOR OUTPUT AS 1',
            b'20 PRINT#1, "cassette test"'
        ]

    def test_cas_save_load(self):
        """Save and load from an existing CAS file."""
        shutil.copy(_input_file('test.cas'), _output_file('test.cas'))
        with Session(devices={b'CAS1:': _output_file('test.cas')}) as s:
            s.execute('save "cas1:empty"')
            s.execute('load "cas1:test"')
            s.execute('list')
            output = [_row.strip() for _row in self.get_text(s)]
        assert output[:3] == [
            b'test    .B Found.',
            b'10 OPEN "output.txt" FOR OUTPUT AS 1',
            b'20 PRINT#1, "cassette test"'
        ]

    def test_cas_current_device(self):
        """Save and load to cassette as current device."""
        with Session(
                devices={b'CAS1:': _output_file('test_current.cas')},
                current_device=b'CAS1:'
            ) as s:
            s.execute('10 ?')
            s.execute('save "Test"')
        with Session(
                devices={b'CAS1:': _output_file('test_current.cas')},
                current_device=b'CAS1:'
            ) as s:
            s.execute('load "Test"')
            s.execute('list')
            output = [_row.strip() for _row in self.get_text(s)]
        assert output[:2] == [
            b'Test    .B Found.',
            b'10 PRINT',
        ]

    def test_cas_text(self):
        """Save and load in plaintext to a CAS file."""
        try:
            os.remove(_output_file('test_prog.cas'))
        except EnvironmentError:
            pass
        with Session(devices={b'CAS1:': _output_file('test_prog.cas')}) as s:
            s.execute('10 A%=1234')
            s.execute('save "cas1:prog",A')
        with Session(devices={b'CAS1:': _output_file('test_prog.cas')}) as s:
            s.execute('run "cas1:prog"')
            output = [_row.strip() for _row in self.get_text(s)]
            assert s.get_variable('A%') == 1234
            assert output[0] == b'prog    .A Found.'

    def test_cas_data(self):
        """Write and read data to a CAS file."""
        try:
            os.remove(_output_file('test_data.cas'))
        except EnvironmentError:
            pass
        with Session(devices={b'CAS1:': _output_file('test_data.cas')}) as s:
            s.execute('open "cas1:data" for output as 1')
            s.execute('print#1, 1234')
        with Session(devices={b'CAS1:': _output_file('test_data.cas')}) as s:
            s.execute('open "cas1:data" for input as 1')
            s.execute('input#1, A%')
            output = [_row.strip() for _row in self.get_text(s)]
            assert s.get_variable('A%') == 1234
            assert output[0] == b'data    .D Found.'

    def test_wav_text(self):
        """Save and load in plaintext to a WAV file."""
        try:
            os.remove(_output_file('test_prog.wav'))
        except EnvironmentError:
            pass
        with Session(devices={b'CAS1:': _output_file('test_prog.wav')}) as s:
            s.execute('10 A%=1234')
            s.execute('save "cas1:prog",A')
        with Session(devices={b'CAS1:': _output_file('test_prog.wav')}) as s:
            s.execute('run "cas1:prog"')
            assert s.get_variable('A%') == 1234

    def test_wav_data(self):
        """Write and read data to a WAV file."""
        try:
            os.remove(_output_file('test_data.wav'))
        except EnvironmentError:
            pass
        with Session(devices={b'CAS1:': _output_file('test_data.wav')}) as s:
            s.execute('open "cas1:data" for output as 1')
            s.execute('print#1, 1234')
        with Session(devices={b'CAS1:': _output_file('test_data.wav')}) as s:
            s.execute('open "cas1:data" for input as 1')
            s.execute('input#1, A%')
            assert s.get_variable('A%') == 1234

    def test_wav_save_load(self):
        """Save and load in to the same WAV file in one session."""
        try:
            os.remove(_output_file('test.wav'))
        except EnvironmentError:
            pass
        # create a WAV file with two programs
        with Session(devices={b'CAS1:': _output_file('test.wav')}) as s:
            s.execute('10 A%=1234')
            s.execute('save "cas1:prog"')
            s.execute('20 A%=12345')
            s.execute('save "cas1:Prog 2",A')
        with Session(devices={b'CAS1:': _output_file('test.wav')}) as s:
            # overwrite (part of) the first program
            s.execute('save "cas1:"')
            # load whatever is next (this should be Prog 2)
            s.execute('run "cas1:"')
            assert s.get_variable('A%') == 12345

    def test_cas_empty(self):
        """Attach empty CAS file."""
        try:
            os.remove(_output_file('empty.cas'))
        except EnvironmentError:
            pass
        # create empty file
        open(_output_file('empty.cas'), 'wb').close()
        with Session(devices={b'CAS1:': _output_file('empty.cas')}) as s:
            s.execute('save "cas1:"')
            s.execute('load "cas1:"')
            output = [_row.strip() for _row in self.get_text(s)]
        # device timeout given at end of tape
        assert output[0] == b'Device Timeout\xff'

    def test_cas_unavailable(self):
        """Try to attach directory as CAS file."""
        try:
            os.rmdir(_output_file('empty'))
        except EnvironmentError:
            pass
        # create empty dir
        os.mkdir(_output_file('empty'))
        with Session(devices={b'CAS1:': _output_file('empty')}) as s:
            s.execute('load "cas1:"')
            output = [_row.strip() for _row in self.get_text(s)]
            assert output[0] == b'Device Unavailable\xff'
            # check internal api function
            assert not s._impl.files.device_available(b'CAS1:')

    def test_cas_already_open(self):
        """Try to open file twice."""
        try:
            os.remove(_output_file('test_data.cas'))
        except EnvironmentError:
            pass
        with Session(devices={b'CAS1:': _output_file('test_data.cas')}) as s:
            s.execute('open "cas1:data" for output as 1')
            s.execute('open "cas1:data" for output as 2')
            output = [_row.strip() for _row in self.get_text(s)]
            assert output[0] == b'File already open\xff'

    def test_cas_bad_name(self):
        """Try to open file with funny name."""
        try:
            os.remove(_output_file('test_data.cas'))
        except EnvironmentError:
            pass
        with Session(devices={b'CAS1:': _output_file('test_data.cas')}) as s:
            s.execute(b'open "cas1:\x02\x01" for output as 1')
            output = [_row.strip() for _row in self.get_text(s)]
            assert output[0] == b'Bad file number\xff'

    def test_cas_bad_mode(self):
        """Try to open file with illegal mode."""
        try:
            os.remove(_output_file('test_data.cas'))
        except EnvironmentError:
            pass
        with Session(devices={b'CAS1:': _output_file('test_data.cas')}) as s:
            s.execute('open "cas1:test" for random as 1')
            output = [_row.strip() for _row in self.get_text(s)]
            assert output[0] == b'Bad file mode\xff'

    def test_cas_bad_operation(self):
        """Try to perform illegal operations."""
        try:
            os.remove(_output_file('test_data.cas'))
        except EnvironmentError:
            pass
        with Session(devices={b'CAS1:': _output_file('test_data.cas')}) as s:
            s.execute('open "cas1:test" for output as 1')
            s.execute('? LOF(1)')
            s.execute('? LOC(1)')
            output = [_row.strip() for _row in self.get_text(s)]
            assert output[:2] == [b'Illegal function call\xff', b'Illegal function call\xff']

    def test_cas_no_name(self):
        """Save and load to cassette without a filename."""
        with Session(devices={b'CAS1:': _output_file('test_current.cas')}) as s:
            s.execute('10 ?')
            s.execute('save "cas1:"')
        with Session(devices={b'CAS1:': _output_file('test_current.cas')}) as s:
            s.execute('load "cas1:"')
            s.execute('list')
            output = [_row.rstrip() for _row in self.get_text(s)]
        assert output[:2] == [
            b'        .B Found.',
            b'10 PRINT',
        ]

if __name__ == '__main__':
    run_tests()
