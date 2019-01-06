"""
PC-BASIC - textbase.py
Text screen helper classes

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ...compat import iterchar
from ..base import signals
from ..base import error
from .. import values


EGA_CURSOR_MODES = (
    'ega', 'mda', 'ega_mono', 'vga', 'olivetti', 'hercules'
)


#######################################################################################
# function key macro guide

class BottomBar(object):
    """Key guide bar at bottom line."""

    def __init__(self):
        """Initialise bottom bar."""
        # use 80 here independent of screen width
        # we store everything in a buffer and only show what fits
        self.clear()
        self.visible = False

    def clear(self):
        """Clear the contents."""
        self._contents = [(b' ', 0)] * 80

    def write(self, s, col, reverse):
        """Write chars on virtual bottom bar."""
        for i, c in enumerate(iterchar(s)):
            self._contents[col + i] = (c, reverse)

    def get_char_reverse(self, col):
        """Retrieve char and reverse attribute."""
        return self._contents[col]


#######################################################################################
# cursor

class Cursor(object):
    """Manage the cursor."""

    def __init__(self, queues, mode, capabilities):
        """Initialise the cursor."""
        self._queues = queues
        self._mode = mode
        # odd treatment of cursors on EGA machines
        self._ega_quirks = capabilities in EGA_CURSOR_MODES
        # do all text modes with >8 pixels have an ega-cursor?
        # cursor on the second last line in EGA mode
        self._ega_cursor = capabilities == 'ega'
        # are we in parse mode? invisible unless visible_run is True
        self._default_visible = True
        # cursor visible in parse mode? user override
        self._visible_run = False
        # actually visible at present
        self._visible = False
        # cursor shape
        self._from_line = 0
        self._to_line = 0
        self._width = self._mode.font_width
        self._height = self._mode.font_height
        self._fore_attr = None
        self._position = 1, 1

    def init_mode(self, mode, attr):
        """Change the cursor for a new screen mode."""
        self._mode = mode
        self._height = mode.font_height
        # set the cursor position and attribute
        self.move(1, 1, attr, new_width=1)
        # cursor width starts out as single char
        self.set_default_shape(True)
        self.reset_visibility()

    def set_attr(self, new_attr):
        """Set the text cursor attribute and submit."""
        row, column = self._position
        self.move(row, column, new_attr, None)

    def show(self, do_show):
        """Force cursor to be visible/invisible."""
        self._visibility = do_show
        self._queues.video.put(signals.Event(signals.VIDEO_SHOW_CURSOR, (do_show,)))

    def move(self, new_row, new_column, new_attr=None, new_width=None):
        """Move the cursor and submit."""
        if new_attr:
            fore, _, _, _ = self._mode.split_attr(new_attr)
        else:
            fore = self._fore_attr
        if not new_width:
            new_width = self._width
        else:
            new_width = new_width * self._mode.font_width
        if (
                (new_row, new_column) == self._position
                and fore == self._fore_attr and new_width == self._width
            ):
            return
        self._position = new_row, new_column
        self._fore_attr = fore
        self._width = new_width
        if self._visible:
            self._queues.video.put(signals.Event(
                signals.VIDEO_MOVE_CURSOR, (new_row, new_column, fore, new_width)
            ))

    def set_visibility(self, visible_run):
        """Set cursor visibility when a program is being run."""
        self._visible_run = visible_run
        self.reset_visibility()

    def reset_visibility(self):
        """Set cursor visibility to its default state."""
        # visible if in interactive mode and invisible when a program is being run
        visible = self._default_visible
        # unless forced to be visible
        # in graphics mode, we can't force the cursor to be visible on execute.
        if self._mode.is_text_mode:
            visible = visible or self._visible_run
        if self._visible != visible:
            self._visible = visible
            self._queues.video.put(signals.Event(signals.VIDEO_SHOW_CURSOR, (visible,)))

    @property
    def shape(self):
        """Cursor shape (from, to)."""
        return self._from_line, self._to_line

    def set_shape(self, from_line, to_line):
        """Set the cursor shape."""
        # A block from from_line to to_line in 8-line modes.
        # Use compatibility algo in higher resolutions
        fx, fy = self._width, self._height
        # odd treatment of cursors on EGA machines,
        # presumably for backward compatibility
        # the following algorithm is based on DOSBox source int10_char.cpp
        #     INT10_SetCursorShape(Bit8u first,Bit8u last)
        if self._ega_quirks:
            max_line = fy - 1
            if from_line & 0xe0 == 0 and to_line & 0xe0 == 0:
                if (to_line < from_line):
                    # invisible only if to_line is zero and to_line < from_line
                    if to_line != 0:
                        # block shape from *to_line* to end
                        from_line = to_line
                        to_line = max_line
                elif ((from_line | to_line) >= max_line or
                            to_line != max_line-1 or from_line != max_line):
                    if to_line > 3:
                        if from_line+2 < to_line:
                            if from_line > 2:
                                from_line = (max_line+1) // 2
                            to_line = max_line
                        else:
                            from_line = from_line - to_line + max_line
                            to_line = max_line
                            if max_line > 0xc:
                                from_line -= 1
                                to_line -= 1
        self._from_line = max(0, min(from_line, fy-1))
        self._to_line = max(0, min(to_line, fy-1))
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_CURSOR_SHAPE, (self._from_line, self._to_line))
        )

    def set_default_shape(self, overwrite_shape):
        """Set the cursor to one of two default shapes."""
        if overwrite_shape:
            if not self._mode.is_text_mode:
                # always a block cursor in graphics mode
                self.set_shape(0, self._height-1)
            elif self._ega_cursor:
                # EGA cursor is on second last line
                self.set_shape(self._height-2, self._height-2)
            elif self._height == 9:
                # Tandy 9-pixel fonts; cursor on 8th
                self.set_shape(self._height-2, self._height-2)
            else:
                # other cards have cursor on last line
                self.set_shape(self._height-1, self._height-1)
        else:
            # half-block cursor for insert
            self.set_shape(self._height//2, self._height-1)

    def rebuild(self):
        """Rebuild the cursor on resume."""
        if self._visible:
            self._queues.video.put(signals.Event(
                signals.VIDEO_SET_CURSOR_SHAPE, (self._from_line, self._to_line)
            ))
            row, column = self._position
            self._queues.video.put(signals.Event(
                signals.VIDEO_MOVE_CURSOR, (row, column, self._fore_attr, self._width)
            ))
        self._queues.video.put(signals.Event(
            signals.VIDEO_SHOW_CURSOR, (self._visible,)
        ))


###############################################################################
# text viewport / scroll area

class ScrollArea(object):
    """Text viewport / scroll area."""

    def __init__(self, mode):
        """Initialise the scroll area."""
        self._height = mode.height
        self.unset()

    def init_mode(self, mode):
        """Initialise the scroll area for new screen mode."""
        self._height = mode.height
        if self._bottom == self._height:
            # tandy/pcjr special case: VIEW PRINT to 25 is preserved
            self.set(1, self._height)
        else:
            self.unset()

    @property
    def active(self):
        """A viewport has been set."""
        return self._active

    @property
    def bounds(self):
        """Return viewport bounds."""
        return self._top, self._bottom

    @property
    def top(self):
        """Return viewport top bound."""
        return self._top

    @property
    def bottom(self):
        """Return viewport bottom bound."""
        return self._bottom

    def set(self, start, stop):
        """Set the scroll area."""
        self._active = True
        # _top and _bottom are inclusive and count rows from 1
        self._top = start
        self._bottom = stop

    def unset(self):
        """Unset scroll area."""
        # there is only one VIEW PRINT setting across all pages.
        # scroll area normally excludes the bottom bar
        self.set(1, self._height - 1)
        self._active = False
