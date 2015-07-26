"""
PC-BASIC - bytestream.py
StringIO-like wrapper for bytearray

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

class ByteStream(object):
    """ StringIO-like wrapper for bytearray. """

    def __init__(self, contents=''):
        """ Create e new ByteStream. """
        self.setvalue(contents)

    def setvalue(self, contents=''):
        """ Assign a bytearray s, move location to 0. This does not create a copy, changes affect the original bytearray. """
        self._contents = contents
        self._loc = 0

    def getvalue(self):
        """ Retrieve the bytearray. changes will affect the bytestream. """
        return self._contents

    def tell(self):
        """ Get the current location. """
        return self._loc

    def seek(self, n_bytes, from_where=0):
        """ Move loc by n bytes from start(w=0), current(w=1) or end(w=2). """
        if from_where == 0:
            self._loc = n_bytes
        elif from_where == 1:
            self._loc += n_bytes
        elif from_where == 2:
            self._loc = len(self._contents)-n_bytes
        if self._loc < 0:
            self._loc = 0
        elif self._loc > len(self._contents):
            self._loc = len(self._contents)

    def read(self, n_bytes=None):
        """ Get an n-length string and move the location n forward. If loc>len, return empty string. """
        if n_bytes is None:
            n_bytes = len(self._contents) - self._loc
        if self._loc >= len(self._contents):
            self._loc = len(self._contents)
            return ''
        peeked = self._contents[self._loc:self._loc+n_bytes]
        self._loc += len(peeked)
        return peeked

    def write(self, substr):
        """ Write a str or bytearray or char s to the current location. Overwrite, do not insert. """
        if self._loc >= len(self._contents):
            self._contents += substr
            self._loc = len(self._contents)
        else:
            self._contents[self._loc:self._loc+len(substr)] = substr
            self._loc += len(substr)

    def truncate(self, n=None):
        """ Clip off the bytearray after position n. """
        if n is None:
            n = self._loc
        self._contents = self._contents[:n]
        if self._loc >= len(self._contents):
            self._loc = len(self._contents)

    def close(self):
        """ Close the stream. """
        pass

    def flush(self):
        """ Flush the stream. """
        pass
