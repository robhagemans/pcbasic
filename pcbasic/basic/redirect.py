"""
PC-BASIC - redirect.py
Output redirection

(c) 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging


class OutputRedirection(object):
    """Manage I/O redirection."""

    def __init__(self, option_output, append, filter_stream):
        """Initialise redirects."""
        # redirect output to file or printer
        self._output_echos = []
        # filter interface depends on redirection output
        if filter_stream:
            self._output_echos.append(filter_stream)
        if option_output:
            mode = b'ab' if append else b'wb'
            try:
                # raw codepage output to file
                self._output_echos.append(open(option_output, mode))
            except EnvironmentError as e:
                logging.warning(u'Could not open output file %s: %s', option_output, e.strerror)

    def write(self, s):
        """Write a string/bytearray to all redirected outputs."""
        for f in self._output_echos:
            f.write(s)

    def toggle_echo(self, stream):
        """Toggle copying of all screen I/O to stream."""
        if stream in self._output_echos:
            self._output_echos.remove(stream)
        else:
            self._output_echos.append(stream)
