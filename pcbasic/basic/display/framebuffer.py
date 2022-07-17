"""
PC-BASIC - display.framebuffer
Emulated video memory

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import functools
import operator

from ...compat import xrange, int2byte, zip, iterbytes

from ..base import bytematrix


# video segment
MDA_SEGMENT = 0xb000
CGA_SEGMENT = 0xb800
EGA_SEGMENT = 0xa000


##############################################################################
# sprites & tiles

class PackedTileBuilder(object):
    """Packed-pixel (CGA) tiles."""

    def __init__(self, bits_per_pixel):
        """Initialise tile builder."""
        self._bitsperpixel = bits_per_pixel

    def __call__(self, pattern):
        """Build a flood-fill tile for CGA screens."""
        # in modes 1, (2), 3, 4, 5, 6 colours are encoded in consecutive bits
        # each byte represents one scan line
        return bytematrix.ByteMatrix.frompacked(
            pattern, height=len(pattern), items_per_byte=8//self._bitsperpixel
        )


class PlanedTileBuilder(object):
    """Interlaced-plane (EGA) tiles."""

    def __init__(self, number_planes):
        """Initialise sprite builder."""
        # number of colour planes
        self._number_planes = number_planes

    def __call__(self, pattern):
        """Build a flood-fill tile."""
        # append nulls until we can cleanly partition into planes
        extra_chars = len(pattern) % self._number_planes
        if extra_chars:
            pattern.extend(bytearray(self._number_planes - extra_chars))
        # unpack bytes into pattern
        allplanes = bytematrix.ByteMatrix.frompacked(
            pattern, height=len(pattern), items_per_byte=8
        )
        planes = (
            allplanes[_plane::self._number_planes, :] << _plane
            for _plane in range(self._number_planes)
        )
        tile = functools.reduce(operator.__ior__, planes)
        return tile


class PackedSpriteBuilder(object):
    """Packed-pixel (CGA) sprite builder."""

    # no width quirks
    width_factor = 1

    def __init__(self, bits_per_pixel):
        self._bitsperpixel = bits_per_pixel

    def pack(self, sprite):
        """Pack the sprite into bytearray."""
        # sprite size record
        size_record = struct.pack('<HH', sprite.width * self._bitsperpixel, sprite.height)
        # interval_to_bytes
        packed = sprite.packed(items_per_byte=8 // self._bitsperpixel)
        return size_record + packed

    def unpack(self, array):
        """Unpack bytearray into sprite."""
        row_bits, height = struct.unpack('<HH', array[0:4])
        width = row_bits // self._bitsperpixel
        row_bytes = (width * self._bitsperpixel + 7) // 8
        byte_size = row_bytes * height
        # bytes_to_interval
        packed = array[4:4+byte_size]
        sprite = bytematrix.ByteMatrix.frompacked(
            packed, height, items_per_byte=8 // self._bitsperpixel
        )
        # clip to requested width
        sprite = sprite[:, :width]
        return sprite


class PlanedSpriteBuilder(object):
    """Sprite builder with interlaced colour planes (EGA sprites)."""

    # no width quirks
    width_factor = 1

    # ** byte mapping for sprites in EGA modes
    # sprites have 8 pixels per byte
    # with colour planes in consecutive rows
    # each new row is aligned on a new byte

    def __init__(self, number_planes):
        """Initialise sprite builder."""
        # number of colour planes
        self._number_planes = number_planes

    def pack(self, sprite):
        """Pack the sprite into bytearray."""
        # extract colour planes
        # note that to get the plane this should be bit-masked - (s >> _p) & 1
        # but bytematrix.packbytes will do this for us
        sprite_planes = (
            (sprite >> _plane)  # & 1
            for _plane in range(self._number_planes)
        )
        # pack the bits into bytes
        #interval_to_bytes
        packed_planes = list(
            _sprite.packed(items_per_byte=8)
            for _sprite in sprite_planes
        )
        # interlace row-by-row
        row_bytes = (sprite.width + 7) // 8
        length = sprite.height * self._number_planes * row_bytes
        interlaced = bytearray().join(
            _packed[_row_offs : _row_offs+row_bytes]
            for _row_offs in range(0, length, row_bytes)
            for _packed in packed_planes
        )
        size_record = struct.pack('<HH', sprite.width, sprite.height)
        return size_record + interlaced

    def unpack(self, array):
        """Build sprite from bytearray in EGA modes."""
        width, height = struct.unpack('<HH', array[:4])
        row_bytes = (width + 7) // 8
        length = height * self._number_planes * row_bytes
        packed = array[4:4+length]
        # ensure iterations over memoryview yield int, not bytes, in Python 2
        packed = iterbytes(packed)
        # unpack all planes
        #bytes_to_interval
        allplanes = bytematrix.ByteMatrix.frompacked(
            packed, height=height*self._number_planes, items_per_byte=8
        )
        # clip to requested width
        allplanes = allplanes[:, :width]
        # de-interlace planes
        sprite_planes = (
            allplanes[_plane::self._number_planes, :] << _plane
            for _plane in range(self._number_planes)
        )
        # combine planes
        sprite = functools.reduce(operator.__ior__, sprite_planes)
        return sprite


class Tandy6SpriteBuilder(PlanedSpriteBuilder):
    """Wrapper for Tandy mode 6's sprite-size record quirks."""

    # width is twice what's recorded
    width_factor = 2

    def pack(self, sprite):
        """Pack sprite, report only half the width packed."""
        record = PlanedSpriteBuilder.pack(self, sprite)
        width = sprite.width // self.width_factor
        width_record = struct.pack('<H', width)
        return width_record + record[2:]

    def unpack(self, array):
        """Unpack sprite, twice the width reported."""
        width, = struct.unpack('<H', array[:2])
        width *= self.width_factor
        size_record = struct.pack('<H', width)
        # explicit conversion to bytes only needed for Python 2, in Python 3 concatenation is ok
        # via bytearray as otherwide it gives str representation in Python 2
        return PlanedSpriteBuilder.unpack(self, size_record + bytes(bytearray(array[2:])))


##############################################################################
# framebuffer memory map

class _MemoryMapper(object):
    """Map between coordinates and locations in the framebuffer."""

    def __init__(
            self, video_mem_size, max_pages, page_size
        ):
        """Initialise video mode settings."""
        # override this
        self._video_segment = None
        self._page_size = page_size
        self._video_mem_size = video_mem_size
        self._max_pages = max_pages

    def set_video_mem_size(self, new_size):
        """Set available video memory."""
        self._video_mem_size = new_size

    @property
    def num_pages(self):
        """Number of available pages."""
        num_pages = self._video_mem_size // self._page_size
        if self._max_pages:
            return min(self._max_pages, num_pages)
        return num_pages

    @property
    def page_size(self):
        """Size in bytes of video page."""
        return self._page_size

    def get_all_memory(self, display):
        """Obtain a copy of all video memory."""
        addr = self._video_segment * 0x10
        buffer = self.get_memory(display, addr, self._video_mem_size)
        return addr, buffer

    def get_memory(self, display, addr, num_bytes):
        """Retrieve bytes from video memory, stub."""

    def set_memory(self, display, addr, bytes):
        """Set bytes in video memory, stub."""


class TextMemoryMapper(_MemoryMapper):
    """Map between coordinates and locations in the textmode framebuffer."""

    def __init__(self, text_height, text_width, video_mem_size, max_pages, is_mono):
        """Initialise video mode settings."""
        page_size = 0x1000 if text_width == 80 else 0x800
        _MemoryMapper.__init__(self, video_mem_size, max_pages, page_size)
        self._video_segment = MDA_SEGMENT if is_mono else CGA_SEGMENT
        self._text_height = text_height
        self._text_width = text_width

    def get_memory(self, display, addr, num_bytes):
        """Retrieve bytes from textmode video memory."""
        addr -= self._video_segment * 0x10
        mem_bytes = bytearray(num_bytes)
        for i in xrange(num_bytes):
            page, offset = divmod(addr+i, self._page_size)
            row, row_offset = divmod(offset, self._text_width*2)
            col = row_offset // 2
            try:
                if (addr+i) % 2:
                    mem_bytes[i] = display.pages[page].get_attr(1 + row, 1 + col)
                else:
                    mem_bytes[i] = display.pages[page].get_byte(1 + row, 1 + col)
            except IndexError:
                pass
        return mem_bytes

    def set_memory(self, display, addr, mem_bytes):
        """Set bytes in textmode video memory."""
        addr -= self._video_segment*0x10
        last_row = 0
        for i in xrange(len(mem_bytes)):
            page, offset = divmod(addr+i, self._page_size)
            row, row_offset = divmod(offset, self._text_width*2)
            col = row_offset // 2
            try:
                if (addr+i) % 2:
                    c = display.pages[page].get_byte(1+row, 1+col)
                    a = mem_bytes[i]
                else:
                    c = mem_bytes[i]
                    a = display.pages[page].get_attr(1+row, 1+col)
                display.pages[page].put_char_attr(1+row, 1+col, int2byte(c), a)
            except IndexError:
                pass
            last_row = 1 + row


class GraphicsMemoryMapper(_MemoryMapper):
    """Map between coordinates and locations in the graphical framebuffer."""

    def __init__(
            self, pixel_height, pixel_width,
            video_mem_size, max_pages, interleave_times, bank_size, bitsperpixel
        ):
        """Initialise video mode settings."""
        page_size = interleave_times * bank_size
        _MemoryMapper.__init__(self, video_mem_size, max_pages, page_size)
        self._pixel_height = pixel_height
        self._pixel_width = pixel_width
        # cga bank_size = 0x2000 interleave_times=2
        self._interleave_times = interleave_times
        self._bank_size = bank_size
        self._bitsperpixel = bitsperpixel
        # number of pixels referenced in each byte of a plane
        self._ppb = 8 // bitsperpixel
        # strides
        self._bytes_per_row = self._pixel_width * bitsperpixel // 8

    def _get_coords(self, addr):
        """Get video page and coordinates for address."""
        # override
        return 0, 0, 0

    def _coord_ok(self, page, x, y):
        """Check if a page and coordinates are within limits."""
        return (
            page >= 0 and page < self.num_pages and
            x >= 0 and x < self._pixel_width and
            y >= 0 and y < self._pixel_height
        )

    def set_plane(self, plane):
        """Set the current colour plane (EGA only)."""

    def set_plane_mask(self, mask):
        """Set the current colour plane mask (EGA only)."""

    def _walk_memory(self, addr, num_bytes, factor=1):
        """Iterate over graphical memory (pixel-by-pixel, contiguous rows)."""
        # factor supports tandy-6 mode, which has 8 pixels per 2 bytes
        # with alternating planes in even and odd bytes (i.e. ppb==8)
        ppb = factor * self._ppb
        page_size = self._page_size // factor
        bank_size = self._bank_size // factor
        row_size = self._bytes_per_row // factor
        # first row
        page, x, y = self._get_coords(addr)
        offset = min(row_size - x//ppb, num_bytes)
        if self._coord_ok(page, x, y):
            yield page, x, y, 0, offset
        # full rows
        bank_offset, page_offset, start_y = 0, 0, y
        while page_offset + bank_offset + offset < num_bytes:
            y += self._interleave_times
            # not an integer number of rows in a bank
            if offset >= bank_size:
                bank_offset += bank_size
                start_y += 1
                offset, y = 0, start_y
                if bank_offset >= page_size:
                    page_offset += page_size
                    page += 1
                    bank_offset, offset = 0, 0
                    y, start_y = 0, 0
            if self._coord_ok(page, 0, y):
                ofs = page_offset + bank_offset + offset
                if ofs + row_size > num_bytes:
                    yield page, 0, y, ofs, num_bytes - ofs
                else:
                    yield page, 0, y, ofs, row_size
            offset += row_size


class CGAMemoryMapper(GraphicsMemoryMapper):
    """Map between coordinates and locations in the CGA framebuffer."""

    def __init__(
            self, pixel_height, pixel_width,
            video_mem_size, max_pages, interleave_times, bank_size, bitsperpixel
        ):
        """Initialise video mode settings."""
        GraphicsMemoryMapper.__init__(
            self, pixel_height, pixel_width,
            video_mem_size, max_pages, interleave_times, bank_size, bitsperpixel
        )
        self._video_segment = CGA_SEGMENT

    def _get_coords(self, addr):
        """Get video page and coordinates for address."""
        addr = int(addr) - self._video_segment * 0x10
        # modes 1-5: interleaved scan lines, pixels sequentially packed into bytes
        page, addr = divmod(addr, self._page_size)
        # 2 x interleaved scan lines of 80bytes
        bank, offset = divmod(addr, self._bank_size)
        row, col = divmod(offset, self._bytes_per_row)
        x = col * 8 // self._bitsperpixel
        y = bank + self._interleave_times * row
        return page, x, y

    def set_memory(self, display, addr, byte_array):
        """Set bytes in CGA memory."""
        for page, x, y, ofs, length in self._walk_memory(addr, len(byte_array)):
            #bytes_to_interval
            pixarray = bytematrix.ByteMatrix.frompacked(
                byte_array[ofs:ofs+length], height=1, items_per_byte=self._ppb
            )
            display.pages[page].pixels[y, x:x+pixarray.width] = pixarray

    def get_memory(self, display, addr, num_bytes):
        """Retrieve bytes from CGA memory."""
        byte_array = bytearray(num_bytes)
        for page, x, y, ofs, length in self._walk_memory(addr, num_bytes):
            #interval_to_bytes
            pixarray = display.pages[page].pixels[y, x:x+length*self._ppb]
            byte_array[ofs:ofs+length] = pixarray.packed(self._ppb)
        return byte_array


class EGAMemoryMapper(GraphicsMemoryMapper):
    """Map between coordinates and locations in the EGA framebuffer."""

    def __init__(
            self, pixel_height, pixel_width,
            video_mem_size, max_pages, interleave_times, bank_size, bitsperpixel
        ):
        """Initialise video mode settings."""
        GraphicsMemoryMapper.__init__(
            self, pixel_height, pixel_width,
            video_mem_size, max_pages, interleave_times, bank_size, bitsperpixel
        )
        self._video_segment = EGA_SEGMENT
        # EGA uses colour planes, 1 bpp for each plane
        # this is used by walk_memory to determine strides
        self._ppb = 8
        self._bytes_per_row = self._pixel_width // 8
        self._planes_used = range(4)
        # additional colour plane mask
        self._master_plane_mask = 0x07
        # current ega memory colour plane to read
        self._plane = 0
        # current ega memory colour planes to write to
        self._plane_mask = 0xff

    def set_planes_used(self, planes_used):
        """EGA specific settings."""
        self._planes_used = planes_used
        # additional colour plane mask
        self._master_plane_mask = sum(2**_plane for _plane in planes_used)

    def set_plane(self, plane):
        """Set the current colour plane."""
        self._plane = plane

    def set_plane_mask(self, mask):
        """Set the current colour plane mask."""
        self._plane_mask = mask

    def _get_coords(self, addr):
        """Get video page and coordinates for address."""
        addr = int(addr) - self._video_segment * 0x10
        # modes 7-9: 1 bit per pixel per colour plane
        page, addr = divmod(addr, self._page_size)
        row, row_offs = divmod(addr, self._bytes_per_row)
        x, y = row_offs*8, row
        return page, x, y

    def get_memory(self, display, addr, num_bytes):
        """Retrieve bytes from EGA memory."""
        plane = self._plane % (max(self._planes_used) + 1)
        byte_array = bytearray(num_bytes)
        if plane not in self._planes_used:
            return byte_array
        for page, x, y, ofs, length in self._walk_memory(addr, num_bytes):
            pixarray = display.pages[page].pixels[y, x:x+length*8]
            byte_array[ofs:ofs+length] = (pixarray >> plane).packed(8)
        return byte_array

    def set_memory(self, display, addr, byte_array):
        """Set bytes in EGA video memory."""
        # EGA memory is planar with memory-mapped colour planes.
        # Within a plane, 8 pixels are encoded into each byte.
        # The colour plane is set through a port OUT and
        # determines which bit of each pixel's attribute is affected.
        mask = self._plane_mask & self._master_plane_mask
        # return immediately for unused colour planes
        if mask == 0:
            return
        for page, x, y, ofs, length in self._walk_memory(addr, len(byte_array)):
            pixarray = (
                bytematrix.ByteMatrix.frompacked(
                    byte_array[ofs:ofs+length], height=1, items_per_byte=8
                ).render(0, mask)
            )
            width = pixarray.width
            substrate = display.pages[page].pixels[y, x:x+width] & ~mask
            display.pages[page].pixels[y, x:x+width] = (pixarray & mask) | substrate


class Tandy6MemoryMapper(GraphicsMemoryMapper):
    """Map between coordinates and locations in the Tandy SCREEN 6 framebuffer."""

    def __init__(
            self, pixel_height, pixel_width,
            video_mem_size, max_pages, interleave_times, bank_size, bitsperpixel
        ):
        """Initialise video mode settings."""
        GraphicsMemoryMapper.__init__(
            self, pixel_height, pixel_width,
            video_mem_size, max_pages, interleave_times, bank_size, bitsperpixel
        )
        self._video_segment = CGA_SEGMENT
        # mode 6: 4x interleaved scan lines, 8 pixels per two bytes,
        # low attribute bits stored in even bytes, high bits in odd bytes.
        self._bytes_per_row = self._pixel_width * 2 // 8

    def _get_coords(self, addr):
        """Get video page and coordinates for address."""
        addr =  int(addr) - self._video_segment * 0x10
        page, addr = divmod(addr, self._page_size)
        # 4 x interleaved scan lines of 160bytes
        bank, offset = divmod(addr, self._bank_size)
        row, col = divmod(offset, self._bytes_per_row)
        x = (col // 2) * 8
        y = bank + 4 * row
        return page, x, y

    def get_memory(self, display, addr, num_bytes):
        """Retrieve bytes from Tandy 640x200x4 """
        # 8 pixels per 2 bytes
        # low attribute bits stored in even bytes, high bits in odd bytes.
        half_len = (num_bytes+1) // 2
        hbytes = bytearray(half_len), bytearray(half_len)
        for parity, byte_array in enumerate(hbytes):
            plane = parity ^ (addr % 2)
            for page, x, y, ofs, length in self._walk_memory(addr, num_bytes, 2):
                pixarray = display.pages[page].pixels[y, x : x + length*self._ppb*2]
                #hbytes[parity][ofs:ofs+length] = interval_to_bytes(pixarray, self._ppb*2, plane)
                byte_array[ofs:ofs+length] = (pixarray >> plane).packed(self._ppb * 2)
        # resulting array may be too long by one byte, so cut to size
        return [_item for _pair in zip(*hbytes) for _item in _pair] [:num_bytes]

    def set_memory(self, display, addr, byte_array):
        """Set bytes in Tandy 640x200x4 memory."""
        hbytes = byte_array[0::2], byte_array[1::2]
        # Tandy-6 encodes 8 pixels per byte, alternating colour planes.
        # I.e. even addresses are 'colour plane 0', odd ones are 'plane 1'
        for parity, half in enumerate(hbytes):
            plane = parity ^ (addr % 2)
            mask = 2 ** plane
            for page, x, y, ofs, length in self._walk_memory(addr, len(byte_array), 2):
                #pixarray = bytes_to_interval(hbytes[parity][ofs:ofs+length], 2*self._ppb, mask)
                pixarray = (
                    bytematrix.ByteMatrix.frompacked(
                        # what's the deal with the empty bytearrays here in some of the tests?
                        half[ofs:ofs+length], height=1, items_per_byte=2*self._ppb
                    ) << plane
                )
                width = pixarray.width
                substrate = display.pages[page].pixels[y, x:x+width] & ~mask
                display.pages[page].pixels[y, x:x+width] = (pixarray & mask) | substrate
