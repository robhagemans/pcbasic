"""
PC-BASIC - display.py
Display helper classes

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

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
                screen.put_char_attr(screen.apagenum, key_row, i+1, c, a, suppress_cli=True)
            screen.apage.row[key_row-1].end = screen.mode.width


#######################################################################################
# palette

class Palette(object):
    """Colour palette."""

    def __init__(self, queues, mode, capabilities, memory):
        """Initialise palette."""
        self.capabilities = capabilities
        self._memory = memory
        self._queues = queues
        self.mode = mode
        self.set_all(mode.palette, check_mode=False)

    def init_mode(self, mode):
        """Initialise for new mode."""
        self.mode = mode
        self.set_all(mode.palette, check_mode=False)

    def set_entry(self, index, colour, check_mode=True):
        """Set a new colour for a given attribute."""
        mode = self.mode
        if check_mode and not self.mode_allows_palette(mode):
            return
        self.palette[index] = colour
        self.rgb_palette[index] = mode.colours[colour]
        if mode.colours1:
            self.rgb_palette1[index] = mode.colours1[colour]
        self._queues.video.put(
            signals.Event(signals.VIDEO_SET_PALETTE, (self.rgb_palette, self.rgb_palette1)))

    def get_entry(self, index):
        """Retrieve the colour for a given attribute."""
        return self.palette[index]

    def set_all(self, new_palette, check_mode=True):
        """Set the colours for all attributes."""
        if check_mode and new_palette and not self.mode_allows_palette(self.mode):
            return
        self.palette = list(new_palette)
        self.rgb_palette = [self.mode.colours[i] for i in self.palette]
        if self.mode.colours1:
            self.rgb_palette1 = [self.mode.colours1[i] for i in self.palette]
        else:
            self.rgb_palette1 = None
        self._queues.video.put(
            signals.Event(signals.VIDEO_SET_PALETTE, (self.rgb_palette, self.rgb_palette1)))

    def mode_allows_palette(self, mode):
        """Check if the video mode allows palette change."""
        # effective palette change is an error in CGA
        if self.capabilities in ('cga', 'cga_old', 'mda', 'hercules', 'olivetti'):
            raise error.BASICError(error.IFC)
        # ignore palette changes in Tandy/PCjr SCREEN 0
        elif self.capabilities in ('tandy', 'pcjr') and mode.is_text_mode:
            return False
        else:
            return True

    def palette_(self, args):
        """PALETTE: assign colour to attribute."""
        attrib = next(args)
        if attrib is not None:
            attrib = values.to_int(attrib)
        colour = next(args)
        if colour is not None:
            colour = values.to_int(colour)
        list(args)
        if attrib is None and colour is None:
            self.set_all(self.mode.palette)
        else:
            # can't set blinking colours separately
            num_palette_entries = self.mode.num_attr if self.mode.num_attr != 32 else 16
            error.range_check(0, num_palette_entries-1, attrib)
            colour = (colour+1) % 256 -1
            error.range_check(-1, len(self.mode.colours)-1, colour)
            if colour != -1:
                self.set_entry(attrib, colour)

    def palette_using_(self, args):
        """PALETTE USING: set palette from array buffer."""
        array_name, start_indices = next(args)
        array_name = self._memory.complete_name(array_name)
        list(args)
        num_palette_entries = self.mode.num_attr if self.mode.num_attr != 32 else 16
        try:
            dimensions = self._memory.arrays.dimensions(array_name)
        except KeyError:
            raise error.BASICError(error.IFC)
        error.throw_if(array_name[-1] != '%', error.TYPE_MISMATCH)
        lst = self._memory.arrays.view_full_buffer(array_name)
        start = self._memory.arrays.index(start_indices, dimensions)
        error.throw_if(self._memory.arrays.array_len(dimensions) - start < num_palette_entries)
        new_palette = []
        for i in range(num_palette_entries):
            offset = (start+i) * 2
            ## signed int, as -1 means don't set
            val, = struct.unpack('<h', lst[offset:offset+2])
            error.range_check(-1, len(self.mode.colours)-1, val)
            new_palette.append(val if val > -1 else self.get_entry(i))
        self.set_all(new_palette)


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
            self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, fore))
        # cursor width starts out as single char
        self.set_default_shape(True)
        self.reset_visibility()

    def reset_attr(self, new_attr):
        """Set the text cursor attribute."""
        if self._mode.is_text_mode:
            self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, new_attr))

    def show(self, do_show):
        """Force cursor to be visible/invisible."""
        self._queues.video.put(signals.Event(signals.VIDEO_SHOW_CURSOR, do_show))

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
        self._queues.video.put(signals.Event(signals.VIDEO_SHOW_CURSOR, visible))

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
