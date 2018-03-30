"""
PC-BASIC - textbase.py
Text screen helper classes

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import signals
from ..base import error
from .. import values


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
        for i, c in enumerate(s):
            self._contents[col + i] = (c, reverse)

    def show(self, on, screen):
        """Switch bottom bar visibility."""
        # tandy can have VIEW PRINT 1 to 25, should raise IFC in that case
        error.throw_if(on and screen.scroll_area.bottom == screen.mode.height)
        self.visible, was_visible = on, self.visible
        if self.visible != was_visible:
            self.redraw(screen)

    def redraw(self, screen):
        """Redraw bottom bar if visible, clear if not."""
        key_row = screen.mode.height
        # Keys will only be visible on the active page at which KEY ON was given,
        # and only deleted on page at which KEY OFF given.
        screen.clear_rows(key_row, key_row)
        if not screen.mode.is_text_mode:
            reverse_attr = screen.attr
        elif (screen.attr >> 4) & 0x7 == 0:
            reverse_attr = 0x70
        else:
            reverse_attr = 0x07
        if self.visible:
            # always show only complete 8-character cells
            # this matters on pcjr/tandy width=20 mode
            for i in range((screen.mode.width//8) * 8):
                c, reverse = self._contents[i]
                a = reverse_attr if reverse else screen.attr
                screen.put_char_attr(screen.apagenum, key_row, i+1, c, a)
            screen.text.pages[screen.apagenum].row[key_row-1].end = screen.mode.width


#######################################################################################
# cursor

class Cursor(object):
    """Manage the cursor."""

    def __init__(self, queues, mode, capabilities):
        """Initialise the cursor."""
        self._queues = queues
        self._mode = mode
        self._capabilities = capabilities
        # are we in parse mode? invisible unless visible_run is True
        self.default_visible = True
        # cursor visible in parse mode? user override
        self.visible_run = False
        # cursor shape
        self.from_line = 0
        self.to_line = 0
        self.width = self._mode.font_width
        self._height = self._mode.font_height

    def init_mode(self, mode, attr):
        """Change the cursor for a new screen mode."""
        self._mode = mode
        self.width = mode.font_width
        self._height = mode.font_height
        # set the cursor attribute
        if not mode.is_text_mode:
            fore, _, _, _ = mode.split_attr(mode.cursor_index or attr)
            self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, (fore,)))
        # cursor width starts out as single char
        self.set_default_shape(True)
        self.reset_visibility()

    def reset_attr(self, new_attr):
        """Set the text cursor attribute."""
        if self._mode.is_text_mode:
            self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, (new_attr,)))

    def show(self, do_show):
        """Force cursor to be visible/invisible."""
        self._queues.video.put(signals.Event(signals.VIDEO_SHOW_CURSOR, (do_show,)))

    def set_visibility(self, visible_run):
        """Set cursor visibility when a program is being run."""
        self.visible_run = visible_run
        self.reset_visibility()

    def reset_visibility(self):
        """Set cursor visibility to its default state."""
        # visible if in interactive mode and invisible when a program is being run
        visible = self.default_visible
        # unless forced to be visible
        # in graphics mode, we can't force the cursor to be visible on execute.
        if self._mode.is_text_mode:
            visible = visible or self.visible_run
        self._queues.video.put(signals.Event(signals.VIDEO_SHOW_CURSOR, (visible,)))

    def set_shape(self, from_line, to_line):
        """Set the cursor shape."""
        # A block from from_line to to_line in 8-line modes.
        # Use compatibility algo in higher resolutions
        fx, fy = self.width, self._height
        # do all text modes with >8 pixels have an ega-cursor?
        if self._capabilities in (
                'ega', 'mda', 'ega_mono', 'vga', 'olivetti', 'hercules'):
            # odd treatment of cursors on EGA machines,
            # presumably for backward compatibility
            # the following algorithm is based on DOSBox source int10_char.cpp
            #     INT10_SetCursorShape(Bit8u first,Bit8u last)
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
        self.from_line = max(0, min(from_line, fy-1))
        self.to_line = max(0, min(to_line, fy-1))
        self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_SHAPE,
                            (self.width, fy, self.from_line, self.to_line)))

    def set_default_shape(self, overwrite_shape):
        """Set the cursor to one of two default shapes."""
        if overwrite_shape:
            if not self._mode.is_text_mode:
                # always a block cursor in graphics mode
                self.set_shape(0, self._height-1)
            elif self._capabilities == 'ega':
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

    def set_width(self, num_chars):
        """Set the cursor with to num_chars characters."""
        new_width = num_chars * self._mode.font_width
        # update cursor shape to new width if necessary
        if new_width != self.width:
            self.width = new_width
            self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_SHAPE,
                    (self.width, self._height, self.from_line, self.to_line)))


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
        #  need this:
        #set_pos(start, 1)
        #  or this:
        #self.overflow = False
        #self._move_cursor(start, 1)

    def unset(self):
        """Unset scroll area."""
        # there is only one VIEW PRINT setting across all pages.
        # scroll area normally excludes the bottom bar
        self.set(1, self._height - 1)
        self._active = False
