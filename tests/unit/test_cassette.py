"""
PC-BASIC test.cassette
Tests for cassette device

(c) 2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os
import shutil

from pcbasic import Session


HERE = os.path.dirname(os.path.abspath(__file__))


def _input_file(name):
    """Test input file."""
    return os.path.join(HERE, 'input', 'cassette', name)

def _output_file(name):
    """Test output file."""
    return os.path.join(HERE, 'output', 'cassette', name)


class CassetteTest(unittest.TestCase):
    """Cassette tests."""

    def test_cas_load(self):
        """Load from a CAS file."""
        with Session(devices={b'CAS1:': _input_file('test.cas')}) as s:
            s.execute('load "cas1:test"')
            s.execute('list')
            output = [_row.strip() for _row in s.get_text()]
        assert output[:4] == [
            'not this.B Skipped.',
            'test    .B Found.',
            '10 OPEN "output.txt" FOR OUTPUT AS 1',
            '20 PRINT#1, "cassette test"'
        ]

    def test_cas_save_load(self):
        """Save and load from an existing CAS file."""
        shutil.copy(_input_file('test.cas'), _output_file('test.cas'))
        with Session(devices={b'CAS1:': _output_file('test.cas')}) as s:
            s.execute('save "cas1:empty"')
            s.execute('load "cas1:test"')
            s.execute('list')
            output = [_row.strip() for _row in s.get_text()]
        assert output[:3] == [
            'test    .B Found.',
            '10 OPEN "output.txt" FOR OUTPUT AS 1',
            '20 PRINT#1, "cassette test"'
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
            output = [_row.strip() for _row in s.get_text()]
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
            output = [_row.strip() for _row in s.get_text()]
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


if __name__ == '__main__':
    unittest.main()
