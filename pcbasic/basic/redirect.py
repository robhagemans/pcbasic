"""
PC-BASIC - redirect.py
Input/output redirection

(c) 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import threading
import logging
import Queue


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



class InputRedirection(object):
    """Manage I/O redirection."""

    def __init__(self, input_streams, lfcrs):
        """Initialise redirects."""
        self._buffer = []
        self._sources = []
        #self._input_stream = unicodepage.CodecStream(codepage, encoding)
        self._input_streams = [f for f in input_streams if f]
        self._lfcrs = [lfcr for (lfcr, f) in zip(lfcrs, input_streams) if f] or [False]*len(self._input_streams)
        self._closed = [False]*len(self._input_streams)
        self._start_threads()

    def _start_threads(self):
        """Start stream reader threads."""
        # allow None as well as empty list
        if not self._input_streams:
            return
        # launch a daemon thread for each source
        for s in self._input_streams:
            # launch a thread to allow nonblocking reads on both Windows and Unix
            queue = Queue.Queue()
            thread = threading.Thread(target=self._process_input, args=(s, queue))
            thread.daemon = True
            thread.start()
            self._sources.append(queue)
            # read as much as we can in advance
            self._drain_source(queue)

    def __getstate__(self):
        """Pickler."""
        pickle_dict = self.__dict__
        # don't pickle the queues
        del pickle_dict['_sources']
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickler."""
        # don't pickle the queues
        self.__dict__ = pickle_dict
        self._sources = []
        self._start_threads()

    def _process_input(self, stream, queue):
        """Process input from stream."""
        # FIXME: do not hardcode encoding
        encoding = 'utf-8'
        while True:
            # blocking read
            instr = stream.readline().decode(encoding, b'replace')
            # TODO: decode .decode(encoding, b'replace')
            # if encoding:
            #     all_input = all_input.decode(encoding, b'replace')
            # else:
            #     # raw input means it's already in the BASIC codepage
            #     # but the keyboard functions use unicode
            #     all_input = self.codepage.str_to_unicode(
            #                     all_input, preserve_control=True)

            if not instr:
                # input stream is closed, stop the thread
                queue.put(None)
                return
            queue.put(instr)

    def _drain_source(self, queue):
        """Read all available characters from a single source, or None if source closed."""
        while True:
            try:
                return queue.get_nowait()
            except Queue.Empty:
                return ''

    def is_closed(self):
        """All input streams have closed."""
        return self._closed and sum(self._closed) == len(self._closed) and not self._buffer

    def read(self, n=0):
        """Read input from sources."""
        # fill buffer
        for i, source in enumerate(self._sources):
            if self._closed[i]:
                continue
            buf = self._drain_source(source)
            if buf is None:
                self._closed[i] = True
            else:
                buf.replace('\r\n', '\r')
                if self._lfcrs[i]:
                    buf = buf.replace('\n', '\r')
                self._buffer.append(buf)
        # if n=0 this will read the whole buffer, which is default behaviour
        self._buffer, chars = self._buffer[:-n], self._buffer[-n:]
        return ''.join(chars)
