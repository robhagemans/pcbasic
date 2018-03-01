"""
PC-BASIC - interface.base
Base classes for video, input and audio handlers

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import Queue
import time
import logging
import threading

from ..basic.base import signals

# message displayed when wiating to close
WAIT_MESSAGE = u'Press a key to close window'


class Interface(object):
    """User interface for PC-BASIC session."""

    # millisecond delay
    delay = 12

    def __init__(self, try_interfaces, audio_override=None, wait=False, **kwargs):
        """Initialise interface."""
        self._input_queue = Queue.Queue()
        self._video_queue = Queue.Queue()
        self._audio_queue = Queue.Queue()
        self._wait = wait
        self._video, self._audio = None, None
        for video, audio in try_interfaces:
            self._video = video_plugins.create(
                    video, self._input_queue, self._video_queue, **kwargs)
            if self._video:
                break
        else:
            # video plugin is necessary, fail without it
            raise InitFailed('Failed to initialise any video plugin.')
        self._audio = audio_plugins.create(
                    audio_override or audio, self._audio_queue, **kwargs)
        if not self._audio:
            # audio fallback to no-plugin
            self._audio = AudioPlugin(self._audio_queue, **kwargs)

    def get_queues(self):
        """Retrieve interface queues."""
        return self._input_queue, self._video_queue, self._audio_queue

    def launch(self, target, **kwargs):
        """Start an interactive interpreter session."""
        thread = threading.Thread(target=self._thread_runner, args=(target,), kwargs=kwargs)
        try:
            # launch the BASIC thread
            thread.start()
            # run the interface
            self.run()
        finally:
            self.quit_input()
            thread.join()

    def _thread_runner(self, target, **kwargs):
        """Session runner."""
        try:
            target(interface=self, **kwargs)
        finally:
            if self._wait:
                self.pause(WAIT_MESSAGE)
            self.quit_output()

    def run(self):
        """Start the main interface event loop."""
        with self._audio:
            with self._video:
                while self._audio.alive or self._video.alive:
                    # ensure both queues are drained
                    self._video.cycle()
                    self._audio.cycle()
                    if not self._audio.playing and not self._video.busy:
                        # nothing to do, come back later
                        self._video.sleep(self.delay)
                    else:
                        # tiny delay; significantly reduces cpu load when playing audio or blinking video
                        self._video.sleep(1)

    def pause(self, message):
        """Pause and wait for a key."""
        self._video_queue.put(signals.Event(signals.VIDEO_SET_CAPTION, (message,)))
        self._video_queue.put(signals.Event(signals.VIDEO_SHOW_CURSOR, (False,)))
        while True:
            signal = self._input_queue.get()
            if signal.event_type in (signals.KEYB_DOWN, signals.KEYB_QUIT):
                break

    def quit_input(self):
        """Send signal through the input queue to quit BASIC."""
        self._input_queue.put(signals.Event(signals.KEYB_QUIT))
        # drain video queue (joined in other thread)
        while not self._video_queue.empty():
            try:
                signal = self._video_queue.get(False)
            except Queue.Empty:
                continue
            self._video_queue.task_done()
        # drain audio queue
        while not self._audio_queue.empty():
            try:
                signal = self._audio_queue.get(False)
            except Queue.Empty:
                continue
            self._audio_queue.task_done()

    def quit_output(self):
        """Send signal through the output queues to quit plugins."""
        self._video_queue.put(signals.Event(signals.VIDEO_QUIT))
        self._audio_queue.put(signals.Event(signals.AUDIO_QUIT))


class InitFailed(Exception):
    """Initialisation failed."""

    def __init__(self, message=''):
        self._message = message

    def __str__(self):
        return self._message


class PluginRegister(object):
    """Plugin register."""

    def __init__(self, name=''):
        """Initialise plugin register."""
        self._name = name
        self._plugins = {}

    def register(self, name):
        """Decorator to register a plugin."""
        def decorated_plugin(cls):
            self._plugins[name] = cls
            return cls
        return decorated_plugin

    def get(self, name):
        """Retrieve plugin."""
        return self._plugins[name]

    def create(self, name, *args, **kwargs):
        """Retieve and initialise plugin."""
        try:
            return self._plugins[name](*args, **kwargs)
        except KeyError:
            if name and name != 'none':
                logging.error('Unknown %s plugin `%s`', self._name, name)
        except InitFailed as e:
            logging.info('Could not initialise %s plugin `%s`: %s', self._name, name, str(e))
        return None


###############################################################################
# video plugin

video_plugins = PluginRegister('video')

class VideoPlugin(object):
    """Base class for display/input interface plugins."""

    def __init__(self, input_queue, video_queue, **kwargs):
        """Setup the interface."""
        self.alive = True
        self.busy = False
        self.input_queue = input_queue
        self.video_queue = video_queue
        self._handlers = {
            signals.VIDEO_SET_MODE: self.set_mode,
            signals.VIDEO_PUT_GLYPH: self.put_glyph,
            signals.VIDEO_CLEAR_ROWS: self.clear_rows,
            signals.VIDEO_SCROLL_UP: self.scroll_up,
            signals.VIDEO_SCROLL_DOWN: self.scroll_down,
            signals.VIDEO_SET_PALETTE: self.set_palette,
            signals.VIDEO_SET_CURSOR_SHAPE: self.set_cursor_shape,
            signals.VIDEO_SET_CURSOR_ATTR: self.set_cursor_attr,
            signals.VIDEO_SHOW_CURSOR: self.show_cursor,
            signals.VIDEO_MOVE_CURSOR: self.move_cursor,
            signals.VIDEO_SET_PAGE: self.set_page,
            signals.VIDEO_COPY_PAGE: self.copy_page,
            signals.VIDEO_SET_BORDER_ATTR: self.set_border_attr,
            signals.VIDEO_SET_COMPOSITE: self.set_composite,
            signals.VIDEO_BUILD_GLYPHS: self.build_glyphs,
            signals.VIDEO_PUT_PIXEL: self.put_pixel,
            signals.VIDEO_PUT_INTERVAL: self.put_interval,
            signals.VIDEO_FILL_INTERVAL: self.fill_interval,
            signals.VIDEO_PUT_RECT: self.put_rect,
            signals.VIDEO_FILL_RECT: self.fill_rect,
            signals.VIDEO_SET_CAPTION: self.set_caption_message,
            signals.VIDEO_SET_CLIPBOARD_TEXT: self.set_clipboard_text,
        }

    # called by Interface

    def cycle(self):
        """Video/input event cycle."""
        if self.alive:
            self._drain_queue()
        if self.alive:
            self._work()
            self._check_input()

    def sleep(self, ms):
        """Sleep a tick"""
        time.sleep(ms/1000.)

    # private methods

    def _drain_queue(self):
        """Drain signal queue."""
        while True:
            try:
                signal = self.video_queue.get(False)
            except Queue.Empty:
                return True
            if signal.event_type == signals.VIDEO_QUIT:
                # close thread after task_done
                self.alive = False
            else:
                try:
                    self._handlers[signal.event_type](*signal.params)
                except KeyError:
                    pass
            self.video_queue.task_done()

    # plugin overrides

    def __exit__(self, type, value, traceback):
        """Close the interface."""

    def __enter__(self):
        """Final initialisation."""
        return self

    def _work(self):
        """Display update cycle."""

    def _check_input(self):
        """Input devices update cycle."""

    # signal handlers

    def set_mode(self, mode_info):
        """Initialise a given text or graphics mode."""

    def set_caption_message(self, msg):
        """Add a message to the window caption."""

    def set_clipboard_text(self, text, mouse):
        """Put text on the clipboard."""

    def set_palette(self, rgb_palette_0, rgb_palette_1):
        """Build the palette."""

    def set_border_attr(self, attr):
        """Change the border attribute."""

    def set_composite(self, on, composite_colors):
        """Enable/disable composite artifacts."""

    def clear_rows(self, back_attr, start, stop):
        """Clear a range of screen rows."""

    def set_page(self, vpage, apage):
        """Set the visible and active page."""

    def copy_page(self, src, dst):
        """Copy source to destination page."""

    def show_cursor(self, cursor_on):
        """Change visibility of cursor."""

    def move_cursor(self, crow, ccol):
        """Move the cursor to a new position."""

    def set_cursor_attr(self, attr):
        """Change attribute of cursor."""

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""

    def put_glyph(
            self, pagenum, row, col, cp, is_fullwidth,
            fore, back, blink, underline, suppress_cli):
        """Put a character at a given position."""

    def build_glyphs(self, new_dict):
        """Build a dict of glyphs for use in text mode."""

    def set_cursor_shape(self, width, height, from_line, to_line):
        """Build a sprite for the cursor."""

    def put_pixel(self, pagenum, x, y, index):
        """Put a pixel on the screen; callback to empty character buffer."""

    def fill_rect(self, pagenum, x0, y0, x1, y1, index):
        """Fill a rectangle in a solid attribute."""

    def fill_interval(self, pagenum, x0, x1, y, index):
        """Fill a scanline interval in a solid attribute."""

    def put_interval(self, pagenum, x, y, colours):
        """Write a list of attributes to a scanline interval."""

    def put_rect(self, pagenum, x0, y0, x1, y1, array):
        """Apply numpy array [y][x] of attribytes to an area."""


###############################################################################
# audio plugin

audio_plugins = PluginRegister('audio')


class AudioPlugin(object):
    """Base class for audio interface plugins."""

    def __init__(self, audio_queue, **kwargs):
        """Setup the audio interface and start the event handling thread."""
        # sound generators for sounds not played yet
        # if not None, something is playing
        self._next_tone = [None, None, None, None]
        self.alive = True
        self.playing = False
        self.audio_queue = audio_queue

    # called by Interface

    def cycle(self):
        """Audio event cycle."""
        if self.alive:
            self._drain_queue()
        if self.alive:
            self.playing = self._next_tone != [None, None, None, None]
            self._work()

    # private methods

    def _drain_queue(self):
        """Drain audio queue."""
        while True:
            try:
                signal = self.audio_queue.get(False)
            except Queue.Empty:
                return
            self.audio_queue.task_done()
            if signal.event_type == signals.AUDIO_STOP:
                self.hush()
            elif signal.event_type == signals.AUDIO_QUIT:
                # close thread
                self.alive = False
            elif signal.event_type == signals.AUDIO_PERSIST:
                self.persist(*signal.params)
            elif signal.event_type == signals.AUDIO_TONE:
                self.tone(*signal.params)
            elif signal.event_type == signals.AUDIO_NOISE:
                self.noise(*signal.params)

    # plugin overrides

    def __exit__(self, type, value, traceback):
        """Close the audio interface."""

    def __enter__(self):
        """Perform any necessary initialisations."""
        return self

    def _work(self):
        """Play some of the sounds queued."""

    # signal handlers

    def hush(self):
        """Be quiet."""

    def persist(self, do_persist):
        """Allow or disallow mixer to quit."""

    def tone(self, voice, frequency, duration, fill, loop, volume):
        """Enqueue a tone."""

    def noise(self, source, frequency, duration, fill, loop, volume):
        """Enqueue a noise."""
