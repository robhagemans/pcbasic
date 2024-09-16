# -*- coding: utf-8 -*-

"""
PC-BASIC test.await main
unit tests for await main script

(c) 2022--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
import io
import sys
import unittest
from tempfile import NamedTemporaryFile

from pcbasic import main
from pcbasic.compat import stdio
from pcbasic.debug import DebugException
from tests.unit.utils import TestCase, run_tests
from pcbasic.compat import PY2, WIN32


class MainTest(TestCase):
    """Unit tests for main script."""

    tag = u'main'

    async def test_version(self):
        """Test version call."""
        # currently can only redirect to bytes io
        output = io.BytesIO()
        with stdio.redirect_output(output, 'stdout'):
            await main('-v')
        assert output.getvalue().startswith(b'PC-BASIC'), output.getvalue()

    async def test_debug_version(self):
        """Test debug version call."""
        # currently can only redirect to bytes io
        output = io.BytesIO()
        with stdio.redirect_output(output, 'stdout'):
            await main('-v', '--debug')
        assert output.getvalue().startswith(b'PC-BASIC'), output.getvalue()

    async def test_usage(self):
        """Test usage call."""
        output = io.BytesIO()
        with stdio.redirect_output(output, 'stdout'):
            await main('-h')
        assert output.getvalue().startswith(b'SYNOPSIS'), output.getvalue()

    async def test_script(self):
        """Test script run."""
        output = io.BytesIO()
        with stdio.redirect_output(output, 'stdout'):
            await main('-nqe', '?1')
        assert output.getvalue() == b' 1 \r\n', output.getvalue()

    # exercise interfaces

    async def test_cli(self):
        """Exercise cli run."""
        with stdio.quiet():
            await main('-bq')

    async def test_text(self):
        """Exercise text-based run."""
        with stdio.quiet():
            await main('-tq')

    async def test_graphical(self):
        """Exercise graphical run."""
        with stdio.quiet():
            await main('-q')

    async def test_bad_interface(self):
        """Exercise run with bad interface."""
        with stdio.quiet():
            await main('--interface=_no_such_interface_', '-q')

    # exercise sound

    @unittest.skip('cutting off sound being played on sdl2 leads to segfaults')
    async def test_cli_beep(self):
        """Exercise cli run."""
        with stdio.quiet():
            await main('-bqe', 'beep')

    @unittest.skip('cutting off sound being played on sdl2 leads to segfaults')
    async def test_graphical_beep(self):
        """Exercise graphical run."""
        with stdio.quiet():
            await main('-qe', 'beep')

    # resume

    async def test_resume_output(self):
        """Test resume with open empty output file."""
        with NamedTemporaryFile('w+b', delete=False) as state_file:
            with stdio.quiet():
                await main(
                    "--exec=A=1:open\"z:output.txt\" for output as 1:SYSTEM",
                    '--mount=z:%s' % self.output_path(), '-n',
                    '--state=%s' % state_file.name,
                )
                await main(
                    '--resume', '--keys=?#1,A:close:system\\r', '-n',
                    '--state=%s' % state_file.name,
                )
        with open(self.output_path('OUTPUT.TXT'), 'rb') as outfile:
            output = outfile.read()
        assert output == b' 1 \r\n\x1a', repr(output)

    async def test_resume_output_used(self):
        """Test resume with open used output file."""
        with NamedTemporaryFile('w+b', delete=False) as state_file:
            with stdio.quiet():
                await main(
                    "--exec=A=1:open\"z:output.txt\" for output as 1:?#1,2:SYSTEM",
                    '--mount=z:%s' % self.output_path(), '-n',
                    '--state=%s' % state_file.name,
                )
                await main(
                    '--resume', '--keys=?#1,A:close:system\\r', '-n',
                    '--state=%s' % state_file.name,
                )
        with open(self.output_path('OUTPUT.TXT'), 'rb') as outfile:
            output = outfile.read()
        assert output == b' 2 \r\n 1 \r\n\x1a', repr(output)

    async def test_resume_input(self):
        """Test resume with open input file."""
        with NamedTemporaryFile('w+b', delete=False) as state_file:
            with stdio.quiet():
                await main(
                    '-n',
                    "--exec=open\"z:test.txt\" for output as 1:?#1,1,2:close:open\"z:test.txt\" for input as 1:input#1,a:SYSTEM",
                    '--mount=z:%s' % self.output_path(),
                    '--state=%s' % state_file.name,
                )
                await main(
                    '--resume', '--keys=input#1,B:close:open "output.txt" for output as 1:?#1, a; b:close:system\\r', '-n',
                    '--state=%s' % state_file.name,
                )
        with open(self.output_path('OUTPUT.TXT'), 'rb') as outfile:
            output = outfile.read()
        assert output == b' 1  2 \r\n\x1a', repr(output)

    async def test_resume_music(self):
        """Test resume with music queue."""
        with NamedTemporaryFile('w+b', delete=False) as state_file:
            with stdio.quiet():
                await main(
                    '--exec=play"mbcdefgab>cdefgab"','-nq',
                    '--mount=z:%s' % self.output_path(),
                    '--state=%s' % state_file.name,
                )
                await main(
                    '--resume',
                    '--state=%s' % state_file.name,
                    '-nk',
                    'q=play(0)\ropen"z:output.txt" for output as 1:?#1,q:close:system\r',
                )
        with open(self.output_path('OUTPUT.TXT'), 'rb') as outfile:
            output = outfile.read()
        assert output == b' 13 \r\n\x1a', repr(output)


class ConvertTest(TestCase):
    """Unit tests for convert script."""

    tag = u'convert'

    async def test_ascii_to_tokenised(self):
        """Test converting raw text to tokenised."""
        with NamedTemporaryFile('w+b', delete=False) as outfile:
            with NamedTemporaryFile('w+b', delete=False) as infile:
                infile.write(b'10 ? 1\r\n\x1a')
                infile.seek(0)
                await main('--convert=b', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            assert outstr == b'\xff\x76\x12\x0a\x00\x91\x20\x12\x00\x00\x00\x1a', outstr

    async def test_ascii_to_protected(self):
        """Test converting raw text to protected."""
        with NamedTemporaryFile('w+b', delete=False) as outfile:
            with NamedTemporaryFile('w+b', delete=False) as infile:
                infile.write(b'10 ? 1\r\n\x1a')
                infile.seek(0)
                await main('--convert=p', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            assert outstr == b'\xfe\xe9\xa9\xbf\x54\xe2\x12\xad\xf1\x89\xf9\x1a', outstr

    async def test_tokenised_to_ascii(self):
        """Test converting tokenised to raw text."""
        with NamedTemporaryFile('w+b', delete=False) as outfile:
            with NamedTemporaryFile('w+b', delete=False) as infile:
                infile.write(b'\xff\x76\x12\x0a\x00\x91\x20\x12\x00\x00\x00\x1a')
                infile.seek(0)
                await main('--convert=a', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            assert outstr == b'10 PRINT 1\r\n\x1a', outstr

    async def test_protected_to_ascii(self):
        """Test converting protected to raw text."""
        with NamedTemporaryFile('w+b', delete=False) as outfile:
            with NamedTemporaryFile('w+b', delete=False) as infile:
                infile.write(b'\xfe\xe9\xa9\xbf\x54\xe2\x12\xad\xf1\x89\xf9\x1a')
                infile.seek(0)
                await main('--convert=a', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            assert outstr == b'10 PRINT 1\r\n\x1a', outstr

    async def test_tokenised_to_protected(self):
        """Test converting tokenised to protected."""
        with NamedTemporaryFile('w+b', delete=False) as outfile:
            with NamedTemporaryFile('w+b', delete=False) as infile:
                infile.write(b'\xff\x76\x12\x0a\x00\x91\x20\x12\x00\x00\x00\x1a')
                infile.seek(0)
                await main('--convert=p', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            # note that the EOF gets encrypted too
            assert outstr == b'\xfe\xe9\xa9\xbf\x54\xe2\x12\xad\xf1\x89\xf9\x73\x1a', outstr

    async def test_protected_to_tokenised(self):
        """Test converting protected to tokenised."""
        with NamedTemporaryFile('w+b', delete=False) as outfile:
            with NamedTemporaryFile('w+b', delete=False) as infile:
                infile.write(b'\xfe\xe9\xa9\xbf\x54\xe2\x12\xad\xf1\x89\xf9\x1a')
                infile.seek(0)
                await main('--convert=b', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            assert outstr == b'\xff\x76\x12\x0a\x00\x91\x20\x12\x00\x00\x00\x1a', outstr

    async def test_default(self):
        """Test converter run."""
        with NamedTemporaryFile('w+b', delete=False) as outfile:
            with NamedTemporaryFile('w+b', delete=False) as infile:
                infile.write(b'\xfe\xe9\xa9\xbf\x54\xe2\x12\xad\xf1\x89\xf9\x1a')
                infile.seek(0)
                await main('--convert', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            assert outstr == b'10 PRINT 1\r\n\x1a', outstr

    @unittest.skipIf(PY2, 'NamedTemoraryFile has no encoding argument in Python 2.')
    async def test_ascii_to_tokenised_encoding(self):
        """Test converting utf-8 text to tokenised."""
        with NamedTemporaryFile('w+b', delete=False) as outfile:
            with NamedTemporaryFile('w+', delete=False, encoding='utf-8') as infile:
                infile.write('10 ? "£"\r\n\x1a')
                infile.seek(0)
                await main('--text-encoding=utf-8', '--convert=b', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            assert outstr == b'\xff\x78\x12\x0a\x00\x91\x20\x22\x9c\x22\x00\x00\x00\x1a', outstr

    async def test_tokenised_to_ascii_encoding(self):
        """Test converting tokenised to latin-1 text."""
        with io.open(
                self.output_path('latin-1.bas'), 'w+', encoding='latin-1', newline=''
            ) as outfile:
            with io.open(self.output_path('bin.bas'), 'w+b') as infile:
                infile.write(b'\xff\x78\x12\x0a\x00\x91\x20\x22\x9c\x22\x00\x00\x00\x1a')
                infile.seek(0)
                await main('--text-encoding=latin-1', '--convert=a', infile.name, outfile.name)
            outfile.seek(0)
            outstr = outfile.read()
            assert outstr == u'10 PRINT "£"\r\n\x1a', repr(outstr)


class DebugTest(TestCase):
    """Unit tests for debugging main calls."""

    tag = u'debug_main'

    async def test_debug_version(self):
        """Test debug version call."""
        # currently can only redirect to bytes io
        output = io.BytesIO()
        with stdio.redirect_output(output, 'stdout'):
            await main('-v', '--debug')
        assert output.getvalue().startswith(b'PC-BASIC')

    async def test_crash_direct(self):
        """Exercise graphical run and trigger bluescreen from direct mode."""
        with NamedTemporaryFile('w+b', delete=False) as state_file:
            with stdio.quiet():
                await main(
                    '--extension=crashtest',
                    '-qe', '_CRASH', '-k', 'system\r'
                    '--state=%s' % state_file,
                )

    async def test_crash_in_program(self):
        """Exercise graphical run and trigger bluescreen from a program line."""
        with NamedTemporaryFile('w+b', delete=False) as state_file:
            with stdio.quiet():
                await main(
                    '--extension=crashtest',
                    '-k', '10 _crash\r20 system\rrun\r',
                    '--state=%s' % state_file,
                )


if __name__ == '__main__':
    run_tests()
