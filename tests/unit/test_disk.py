"""
PC-BASIC test.disk
Tests for disk devices

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
    return os.path.join(HERE, 'input', 'disk', name)

def _output_file(name):
    """Test output file."""
    return os.path.join(HERE, 'output', 'disk', name)


class DiskTest(unittest.TestCase):
    """Disk tests."""

    def setUp(self):
        """Ensure output directory exists."""
        try:
            os.mkdir(_output_file(u''))
        except EnvironmentError:
            pass

    def test_text(self):
        """Save and load in plaintext to a file."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('10 A%=1234')
            s.execute('save "prog",A')
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('run "prog"')
            assert s.get_variable('A%') == 1234

    def test_binary(self):
        """Save and load in binary format to a file."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('10 A%=1234')
            s.execute('save "prog"')
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('run "prog"')
            assert s.get_variable('A%') == 1234

    def test_protected(self):
        """Save and load in protected format to a file."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('10 A%=1234')
            s.execute('save "prog", P')
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('run "prog"')
            assert s.get_variable('A%') == 1234

    def test_text_letter(self):
        """Save and load in plaintext to a file, explicit drive letter."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('10 A%=1234')
            s.execute('save "A:prog",A')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('run "A:prog"')
            assert s.get_variable('A%') == 1234

    def test_files(self):
        """Test directory listing, current directory and free space report."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('save "A:prog",A')
            s.execute('files "A:"')
            s.execute('print "##"')
            output = [_row.strip() for _row in s.get_text()]
            assert output[:2] == [
                b'A:\\',
                b'.   <DIR>         ..  <DIR> PROG    .BAS'
            ]
            assert output[2].endswith(b' Bytes free')
            # empty line between files and next output
            assert output[3:5] == [b'', b'##']
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('files')
            output = [_row.strip() for _row in s.get_text()]
            assert output[:2] == [
                b'A:\\',
                b'.   <DIR>         ..  <DIR> PROG    .BAS'
            ]

    def test_files_longname(self):
        """Test directory listing with long name."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        open(os.path.join(test_dir, 'very_long_name_and.extension'), 'w')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('files "A:"')
            output = [_row.strip() for _row in s.get_text()]
            assert output[:2] == [
                b'A:\\',
                b'.   <DIR>         ..  <DIR> very_lo+.ex+'
            ]

    def test_files_wildcard(self):
        """Test directory listing with wildcards."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        open(os.path.join(test_dir, 'aaa.txt'), 'w')
        open(os.path.join(test_dir, 'aab.txt'), 'w')
        open(os.path.join(test_dir, 'abc.txt'), 'w')
        open(os.path.join(test_dir, 'aa_long_file_name.txt'), 'w')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('files "A:*.txt"')
            output = [_row.strip() for _row in s.get_text()]
        assert output[1] == b'AAA     .TXT      AAB     .TXT      ABC     .TXT      aa_long+.txt'
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('files "A:aa?.txt"')
            output = [_row.strip() for _row in s.get_text()]
        assert output[1] == b'AAA     .TXT      AAB     .TXT'

    def test_internal_disk_files(self):
        """Test directory listing, current directory and free space report on special @: disk."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'@': (test_dir, u'')}) as s:
            s.execute('save "@:prog",A')
            s.execute('files "@:"')
            output = [_row.strip() for _row in s.get_text()]
            assert output[:2] == [
                b'@:\\',
                b'.   <DIR>         ..  <DIR> PROG    .BAS'
            ]
            assert output[2].endswith(b' Bytes free')

    def test_internal_disk_unbound_files(self):
        """Test directory listing, current directory and free space report on unbound @: disk."""
        with Session(mount={}) as s:
            s.execute('save "@:prog",A')
            s.execute('files "@:"')
            output = [_row.strip() for _row in s.get_text()]
            assert output[:4] == [
                b'Path not found\xff',
                b'@:\\',
                b'.   <DIR>         ..  <DIR>',
                b'0 Bytes free'
            ]

    def test_disk_data(self):
        """Write and read data to a text file."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:data" for output as 1')
            s.execute('print#1, 1234')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:data" for input as 1')
            s.execute('input#1, A%')
            assert s.get_variable('A%') == 1234

    def test_disk_data_utf8(self):
        """Write and read data to a text file, utf-8 encoding."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}, textfile_encoding='utf-8') as s:
            s.execute('open "a:data" for output as 1')
            s.execute('print#1, "\x9C"')
        # utf8-sig, followed by pound sign
        assert open(os.path.join(test_dir, 'DATA'), 'rb').read() == b'\xef\xbb\xbf\xc2\xa3\r\n\x1a'
        with Session(mount={b'A': (test_dir, u'')}, textfile_encoding='utf-8') as s:
            s.execute('open "a:data" for append as 1')
            s.execute('print#1, "\x9C"')
        assert open(os.path.join(test_dir, 'DATA'), 'rb').read() == (
            b'\xef\xbb\xbf\xc2\xa3\r\n\xc2\xa3\r\n\x1a'
        )

    def test_disk_data_lf(self):
        """Write and read data to a text file, soft and hard linefeed."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with open(os.path.join(test_dir, 'DATA'), 'wb') as f:
            f.write('a\nb\r\nc')
        with Session(mount={b'A': (test_dir, u'')}, soft_linefeed=True) as s:
            s.execute('open "a:data" for input as 1')
            s.execute('line input#1, a$')
            s.execute('line input#1, b$')
            s.execute('line input#1, c$')
        assert s.get_variable('A$') == b'a\nb'
        assert s.get_variable('B$') == b'c'
        assert s.get_variable('C$') == b''
        with Session(mount={b'A': (test_dir, u'')}, soft_linefeed=False) as s:
            s.execute('open "a:data" for input as 1')
            s.execute('line input#1, a$')
            s.execute('line input#1, b$')
            s.execute('line input#1, c$')
        assert s.get_variable('A$') == b'a'
        assert s.get_variable('B$') == b'b'
        assert s.get_variable('C$') == b'c'

    def test_disk_data_append(self):
        """Append data to a text file."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:data" for output as 1')
            s.execute('print#1, 1234')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:data" for append as 1')
            s.execute('print#1, "abcde"')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:data" for input as 1')
            s.execute('line input#1, a$')
            s.execute('line input#1, b$')
            assert s.get_variable('A$') == b' 1234 '
            assert s.get_variable('B$') == b'abcde'

    def test_disk_random(self):
        """Write and read data to a random access file."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:data" for random as 1')
            s.execute('field#1, 20 as a$, 20 as b$')
            s.execute('lset b$="abcde"')
            s.execute('print#1, 1234')
            s.execute('put#1, 1')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:data" for random as 1')
            s.execute('field#1, 20 as a$, 20 as b$')
            s.execute('get#1, 1')
            assert s.get_variable('A$') == b' 1234 \r\n'.ljust(20, b'\0')
            assert s.get_variable('B$') == b'abcde'.ljust(20, b' ')

    def test_match_name(self):
        """Test case-insensitive matching of native file name."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        # this will be case sensitive on some platforms but should be picked up correctly anyway
        open(os.path.join(test_dir, 'MixCase.txt'), 'w')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:mixcase.txt" for output as 1')
            s.execute('print#1, 1234')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            s.execute('open "a:MIXCASE.TXT" for input as 1')
            s.execute('input#1, A%')
            assert s.get_variable('A%') == 1234
        # check we've used the pre-existing file
        assert open(os.path.join(test_dir, 'MixCase.txt'), 'rb').read() == ' 1234 \r\n\x1a'

    def test_match_name_non_ascii(self):
        """Test non-matching of names that are not ascii."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        # this will be case sensitive on some platforms but should be picked up correctly anyway
        open(os.path.join(test_dir, u'MY\xc2\xa30.02'), 'w')
        with Session(mount={b'A': (test_dir, u'')}) as s:
            # non-ascii not allowed
            s.execute('open "a:MY\x9c0.02" for output as 1')
            # search for a match in the presence of non-ascii files
            s.execute('open "a:MY0.02" for input as 1')
            output = [_row.strip() for _row in s.get_text()]
        assert output[:2] == [b'Bad file name\xff', b'File not found\xff']

    def test_name_illegal_chars(self):
        """Test non-matching of names that are not ascii."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            # control chars not allowed
            s.execute('open chr$(0) for output as 1')
            s.execute('open chr$(1) for output as 1')
            output = [_row.strip() for _row in s.get_text()]
        # NOTE: gw raises bad file number instead
        assert output[:2] == [b'Bad file name\xff', b'Bad file name\xff']

    def test_name_slash(self):
        """Test non-matching of names with forward slash."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            # forward slash not allowed
            s.execute('open "b/c" for output as 1')
            output = [_row.strip() for _row in s.get_text()]
        # NOTE: gw raises bad file number instead
        assert output[0] == b'Path not found\xff'

    def test_unavailable_drive(self):
        """Test attempt to access unavailable drive letter."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}) as s:
            # drive b: not mounted
            s.execute('open "b:test" for output as 1')
            output = [_row.strip() for _row in s.get_text()]
        assert output[0] == b'Path not found\xff'

    def test_path(self):
        """Test accessing file through path."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        os.mkdir(os.path.join(test_dir, 'a'))
        os.mkdir(os.path.join(test_dir, 'a', 'B'))
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            # simple relative path
            s.execute('open "a\\b\\rel" for output as 1:close')
            # convoluted path
            s.execute('open "a\\b\\..\\..\\a\\.\\dots" for output as 1:close')
            # set cwd
            s.execute('chdir "a"')
            # absolute path
            s.execute('open "\\a\\b\\abs" for output as 1:close')
            # relative path from cwd
            s.execute('open ".\\this" for output as 1:close')
            s.execute('open "..\\parent" for output as 1:close')
        assert os.path.isfile(os.path.join(test_dir, 'a', 'B', 'REL'))
        assert os.path.isfile(os.path.join(test_dir, 'a', 'DOTS'))
        assert os.path.isfile(os.path.join(test_dir, 'a', 'B', 'ABS'))
        assert os.path.isfile(os.path.join(test_dir, 'PARENT'))
        assert os.path.isfile(os.path.join(test_dir, 'a', 'THIS'))

    def test_directory_ops(self):
        """Test directory operations."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('mkdir "test"')
            s.execute('mkdir "test\\test2"')
            s.execute('chdir "test"')
            s.execute('mkdir "remove"')
            s.execute('rmdir "remove"')
        assert os.path.isdir(os.path.join(test_dir, 'TEST'))
        assert os.path.isdir(os.path.join(test_dir, 'TEST', 'TEST2'))
        assert not os.path.exists(os.path.join(test_dir, 'TEST', 'REMOVE'))

    def test_file_ops(self):
        """Test file operations."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        open(os.path.join(test_dir, 'testfile'), 'w').close()
        open(os.path.join(test_dir, 'delete.txt'), 'w').close()
        open(os.path.join(test_dir, 'delete1.txt'), 'w').close()
        open(os.path.join(test_dir, 'delete2.txt'), 'w').close()
        open(os.path.join(test_dir, 'delete3'), 'w').close()
        with Session(
                mount={b'A': (test_dir, u''), b'B': (test_dir, u'')}, current_device='A:'
            ) as s:
            s.execute('name "testfile" as "newname"')
            # rename across disks
            s.execute('name "newname" as "b:fail"')
            # file already exists
            s.execute('name "newname" as "delete.txt"')
            s.execute('kill "delete.txt"')
            s.execute('kill "delete?.txt"')
            s.execute('kill "delete*"')
            # file not found
            s.execute('kill "notfound"')
            # file not found
            s.execute('kill "not*.*"')
            output = [_row.strip() for _row in s.get_text()]
        assert output[:4] == [
            b'Rename across disks\xff',
            b'File already exists\xff',
            b'File not found\xff',
            b'File not found\xff'
        ]
        assert os.path.isfile(os.path.join(test_dir, 'NEWNAME'))
        assert not os.path.exists(os.path.join(test_dir, 'testfile'))
        assert not os.path.exists(os.path.join(test_dir, 'delete.txt'))
        assert not os.path.exists(os.path.join(test_dir, 'delete1.txt'))
        assert not os.path.exists(os.path.join(test_dir, 'delete2.txt'))
        assert not os.path.exists(os.path.join(test_dir, 'delete3'))

    def test_files_cwd(self):
        """Test directory listing, not on root."""
        test_dir = _output_file(u'test_dir')
        try:
            shutil.rmtree(test_dir)
        except EnvironmentError:
            pass
        os.mkdir(test_dir)
        os.mkdir(os.path.join(test_dir, 'a'))
        with Session(mount={b'A': (test_dir, u'')}, current_device='A:') as s:
            s.execute('chdir "a"')
            s.execute('files')
            s.execute('files ".."')
            s.execute('files "..\\"')
            output = [_row.strip() for _row in s.get_text()]
        assert output[:2] == [b'A:\\A', b'.   <DIR>         ..  <DIR>']
        assert output[4:6] == [b'A:\\A', b'.   <DIR>']
        assert output[8:10] == [b'A:\\A', b'.   <DIR>         ..  <DIR> A           <DIR>']

if __name__ == '__main__':
    unittest.main()
