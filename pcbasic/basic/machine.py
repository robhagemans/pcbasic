"""
PC-BASIC - machine.py
Machine emulation and memory model

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import logging

from ..compat import iteritems, int2byte

from .data import NAME, VERSION, COPYRIGHT
from .base import error
from . import values
from . import devices
from .display import modes


# ROM copyright notice
NOTICE = bytearray(
    b'%s %s\r%s\r' % tuple(_.encode('ascii', 'ignore') for _ in (NAME, VERSION, COPYRIGHT))
)


###############################################################################

class MachinePorts(object):
    """Machine ports."""

    # time delay for port value to drop to 0 on maximum reading.
    #  use 100./255. for 100ms.
    joystick_time_factor = 75. / 255.

    def __init__(self, queues, values, display, keyboard, stick, files):
        """Initialise machine ports."""
        self._values = values
        self._queues = queues
        self._keyboard = keyboard
        self._stick = stick
        self._display = display
        # parallel port base address:
        # http://retired.beyondlogic.org/spp/parallel.htm
        # 3BCh - 3BFh  Used for Parallel Ports which were incorporated on to Video Cards
        #              - Doesn't support ECP addresses
        # 378h - 37Fh  Usual Address For LPT 1
        # 278h - 27Fh  Usual Address For LPT 2
        self.lpt_device = [files.get_device(b'LPT1:'), files.get_device(b'LPT2:')]
        # serial port base address:
        # http://www.petesqbsite.com/sections/tutorials/zines/qbnews/9-com_ports.txt
        #            COM1             &H3F8
        #            COM2             &H2F8
        #            COM3             &H3E8 (not implemented)
        #            COM4             &H2E8 (not implemented)
        self.com_base = {0x3f8: 0, 0x2f8: 1}
        self.com_device = [files.get_device(b'COM1:'), files.get_device(b'COM2:')]
        self.com_enable_baud_write = [False, False]
        self.com_baud_divisor = [0, 0]
        self.com_break = [False, False]

    def usr_(self, args):
        """USR: get value of machine-code function; not implemented."""
        num, = args
        logging.warning('USR function not implemented.')
        raise error.BASICError(error.IFC)

    def inp_(self, args):
        """INP: get value from machine port."""
        num, = args
        port = values.to_int(num, unsigned=True)
        inp = self.inp(port)
        # return as unsigned int
        if inp < 0:
            inp += 0x10000
        return self._values.new_integer().from_int(inp)

    def inp(self, port):
        """Get the value in an emulated machine port."""
        keyboard = self._keyboard
        stick = self._stick
        # keyboard
        if port == 0x60:
            return keyboard.last_scancode
        # game port (joystick)
        elif port == 0x201:
            value = (
                (not stick.is_firing[0][0]) * 0x40 +
                (not stick.is_firing[0][1]) * 0x20 +
                (not stick.is_firing[1][0]) * 0x10 +
                (not stick.is_firing[1][1]) * 0x80)
            decay = stick.decay()
            if decay < stick.axis[0][0] * self.joystick_time_factor:
                value += 0x04
            if decay < stick.axis[0][1] * self.joystick_time_factor:
                value += 0x02
            if decay < stick.axis[1][0] * self.joystick_time_factor:
                value += 0x01
            if decay < stick.axis[1][1] * self.joystick_time_factor:
                value += 0x08
            return value
        elif port in (0x379, 0x279):
            # parallel port input ports
            # http://www.aaroncake.net/electronics/qblpt.htm
            # http://retired.beyondlogic.org/spp/parallel.htm
            lpt_port_nr = 0 if port >= 0x378 else 1
            base_addr = {0: 0x378, 1: 0x278}
            if self.lpt_device[lpt_port_nr].stream is None:
                return 0
            # get status port
            busy, ack, paper, select, err = self.lpt_device[lpt_port_nr].stream.get_status()
            return busy * 0x80 | ack * 0x40 | paper * 0x20 | select * 0x10 | err * 0x8
        else:
            # serial port machine ports
            # http://www.qb64.net/wiki/index.php/Port_Access_Libraries#Serial_Communication_Registers
            # http://control.com/thread/1026221083
            for base_addr, com_port_nr in iteritems(self.com_base):
                com_port = self.com_device[com_port_nr]
                if not com_port.available():
                    continue
                # Line Control Register: base_address + 3 (r/w)
                if port == base_addr + 3:
                    _, parity, bytesize, stopbits = com_port.get_params()
                    value = self.com_enable_baud_write[com_port_nr] * 0x80
                    value += self.com_break[com_port_nr] * 0x40
                    value += {b'S': 0x38, b'M': 0x28, b'E': 0x18, b'O': 0x8, b'N': 0}[parity]
                    if stopbits > 1:
                        value += 0x4
                    value += bytesize - 5
                    return value
                # Line Status Register: base_address + 5 (read only)
                elif port == base_addr + 5:
                    # bit 6: data holding register empty
                    # bit 5: transmitter holding register empty
                    # distinction between bit 5 and 6 not implemented
                    # bit 0: data ready
                    # other bits not implemented:
                    #   1 - overrun, 2 - parity 3 - framing errors;
                    #   4 - break interrupt; 7 - at least one error in received FIFO
                    in_waiting, out_waiting = com_port.io_waiting()
                    return (1-out_waiting) * 0x60 + in_waiting
                # Modem Status Register: base_address + 6 (read only)
                elif port == base_addr + 6:
                    cd, ri, dsr, cts = com_port.get_pins()
                    # delta bits not implemented
                    return (cd*0x80 + ri*0x40 + dsr*0x20 + cts*0x10)
            # addr isn't one of the covered ports
            return 0

    def out_(self, args):
        """OUT: send a byte to a machine port."""
        addr = values.to_int(next(args), unsigned=True)
        val = values.to_int(next(args))
        error.range_check(0, 255, val)
        list(args)
        if addr == 0x201:
            # game port reset
            self._stick.reset_decay()
        elif addr == 0x3c5:
            # officially, requires OUT &H3C4, 2 first (not implemented)
            self._display.mode.memorymap.set_plane_mask(val)
        elif addr == 0x3cf:
            # officially, requires OUT &H3CE, 4 first (not implemented)
            self._display.mode.memorymap.set_plane(val)
        elif addr == 0x3d8:
            # CGA mode control register, see http://www.seasip.info/VintagePC/cga.html
            # bit 5 - enable blink (1) show blink as bright background (0) (not implemented)
            # bit 4 - select 640x200x2 mode (not implemented)
            # bit 3 - (1) enable video output (0) disable, show all as background (not implemented)
            # bit 2 - (1) disable colorburst (0) enable colorburst
            # bit 1 - (1) graphics mode (0) text mode (not implemented)
            # bit 0 - high resolution text (?) (not implemented)
            #OUT &H3D8,&H1A: REM enable color burst
            #OUT &H3D8,&H1E: REM disable color burst
            # 0x1a == 0001 1010     0x1e == 0001 1110
            self._display.colourmap.set_colorburst(val & 4 == 0)
        elif addr == 0x3d9:
            # CGA colour control register, see http://www.seasip.info/VintagePC/cga.html
            # bit 5 - palette 0 = r/g/y 1 = c/m/y/k (320x200x4 only)
            # bit 4 - 1 = high intensity 0 = low intensity (320x200x4 only)
            # bits 3-0: Border / Background / Foreground (not implemented)
            #    These 4 bits select one of the 16 CGA colours
            #    (bit 3 = Intensity, Bit 2 = Red, Bit 1 = Green, Bit 0 = Blue).
            #    In text modes, this colour is used for the border (overscan).
            #    In 320x200 graphics modes, it is used for the background and border.
            #    In 640x200 mode, it is used for the foreground colour.
            self._display.colourmap.set_cga4_palette(bool(val & 0x10))
            self._display.colourmap.set_cga4_intensity(bool(val & 0x8))
        elif addr in (0x378, 0x37A, 0x278, 0x27A):
            # parallel port output ports
            # http://www.aaroncake.net/electronics/qblpt.htm
            # http://retired.beyondlogic.org/spp/parallel.htm
            lpt_port_nr = 0 if addr >= 0x378 else 1
            base_addr = {0: 0x378, 1: 0x278}
            if self.lpt_device[lpt_port_nr].stream is None:
                return
            if addr - base_addr[lpt_port_nr] == 0:
                # set data port
                self.lpt_device[lpt_port_nr].stream.write(int2byte(val))
            else:
                # set control port
                self.lpt_device[lpt_port_nr].stream.set_control(
                    select=val & 0x8, init=val&0x4, lf=val&0x2, strobe=val&0x1
                )
        else:
            # serial port machine ports
            # http://www.qb64.net/wiki/index.php/Port_Access_Libraries#Serial_Communication_Registers
            # http://control.com/thread/1026221083
            for base_addr, com_port_nr in iteritems(self.com_base):
                com_port = self.com_device[com_port_nr]
                if not com_port.available():
                    continue
                # ports at base addr and the next one are used for writing baud rate
                # (among other things that aren't implemented)
                if addr in (base_addr, base_addr+1) and self.com_enable_baud_write[com_port_nr]:
                    if addr == base_addr:
                        self.com_baud_divisor[com_port_nr] = (
                            (self.com_baud_divisor[com_port_nr] & 0xff00) + val
                        )
                    elif addr == base_addr + 1:
                        self.com_baud_divisor[com_port_nr] = (
                            val*0x100 + (self.com_baud_divisor[com_port_nr] & 0xff)
                        )
                    if self.com_baud_divisor[com_port_nr]:
                        baudrate, parity, bytesize, stopbits = com_port.get_params()
                        baudrate = 115200 // self.com_baud_divisor[com_port_nr]
                        com_port.set_params(baudrate, parity, bytesize, stopbits)
                # Line Control Register: base_address + 3 (r/w)
                elif addr == base_addr + 3:
                    baudrate, parity, bytesize, stopbits = com_port.get_params()
                    if val & 0x80:
                        self.com_enable_baud_write[com_port_nr] = True
                    # break condition
                    self.com_break[com_port_nr] = (val & 0x40) != 0
                    # parity
                    parity = {0x38: b'S', 0x28: b'M', 0x18: b'E', 0x8: b'O', 0: b'N'}[val&0x38]
                    # stopbits
                    if val & 0x4:
                        # 2 or 1.5 stop bits
                        stopbits = 2
                    else:
                        # 1 stop bit
                        stopbits = 1
                    # set byte size to 5, 6, 7, 8
                    bytesize = (val & 0x3) + 5
                    com_port.set_params(baudrate, parity, bytesize, stopbits)
                    com_port.set_pins(brk=self.com_break[com_port_nr])
                # Modem Control Register: base_address + 4 (r/w)
                elif addr == base_addr + 4:
                    com_port.set_pins(rts=val & 0x2, dtr=val & 0x1)

    def wait_(self, args):
        """WAIT: wait for a machine port."""
        addr = values.to_int(next(args), unsigned=True)
        ander = values.to_int(next(args))
        error.range_check(0, 255, ander)
        xorer = next(args)
        if xorer is None:
            xorer = 0
        else:
            xorer = values.to_int(xorer)
        error.range_check(0, 255, xorer)
        list(args)
        while (self.inp(addr) ^ xorer) & ander == 0:
            self._queues.wait()


###############################################################################
# Memory

class Memory(object):
    """Memory model."""

    # lowest (EGA) video memory address; max 128k reserved for video
    video_segment = 0xa000
    # read only memory
    rom_segment = 0xf000
    # segment that holds ram font
    ram_font_segment = 0xc000

    # where to find the rom font (chars 0-127)
    rom_font_addr = 0xfa6e
    # where to find the ram font (chars 128-254)
    ram_font_addr = 0x500

    key_buffer_offset = 30
    blink_enabled = True

    def __init__(
            self, values, data_memory, files, display, keyboard,
            font_8, interpreter, peek_values, syntax
        ):
        """Initialise memory."""
        self._values = values
        # data segment initialised elsewhere
        self._memory = data_memory
        # device access needed for COM and LPT ports
        # files access for BLOAD and BSAVE
        self._files = files
        # screen access needed for video memory
        self._display = display
        # keyboard buffer access
        self.keyboard = keyboard
        # interpreter, for runmode check
        self.interpreter = interpreter
        # 8-pixel font
        self.font_8 = font_8
        # initial DEF SEG
        self.segment = self._memory.data_segment
        # pre-defined PEEK outputs
        self._peek_values = peek_values
        # tandy syntax
        self._syntax = syntax

    def peek_(self, args):
        """PEEK: Retrieve the value at an emulated memory location."""
        addr, = args
        # no peeking the program code (or anywhere) in protected mode
        if self._memory.program.protected and not self.interpreter.run_mode:
            raise error.BASICError(error.IFC)
        addr = values.to_int(addr, unsigned=True)
        addr += self.segment * 0x10
        return self._values.new_integer().from_int(self._get_memory(addr))

    def poke_(self, args):
        """POKE: Set the value at an emulated memory location."""
        addr = values.to_int(next(args), unsigned=True)
        if self._memory.program.protected and not self.interpreter.run_mode:
            raise error.BASICError(error.IFC)
        val, = args
        val = values.to_int(val)
        error.range_check(0, 255, val)
        if addr < 0:
            addr += 0x10000
        addr += self.segment * 0x10
        self._set_memory(addr, val)

    def bload_(self, args):
        """BLOAD: Load a file into a block of memory."""
        if self._memory.program.protected and not self.interpreter.run_mode:
            raise error.BASICError(error.IFC)
        name = values.next_string(args)
        offset = next(args)
        if offset is not None:
            offset = values.to_int(offset, unsigned=True)
        list(args)
        with self._files.open(0, name, filetype=b'M', mode=b'I') as g:
            # size gets ignored; even the \x1a at the end gets dumped onto the screen.
            seg = g.seg
            if offset is None:
                offset = g.offset
            buf = bytearray(g.read())
            # remove any EOF marker at end
            if buf and buf[-1] == 0x1a:
                buf = buf[:-1]
            # Tandys repeat the header at the end of the file
            if self._syntax == 'tandy':
                buf = buf[:-7]
            addr = seg * 0x10 + offset
            self._set_memory_block(addr, buf)

    def bsave_(self, args):
        """BSAVE: Save a block of memory into a file."""
        if self._memory.program.protected and not self.interpreter.run_mode:
            raise error.BASICError(error.IFC)
        name = values.next_string(args)
        offset = values.to_int(next(args), unsigned=True)
        length = values.to_int(next(args), unsigned=True)
        list(args)
        with self._files.open(
                    0, name, filetype=b'M', mode=b'O',
                    seg=self.segment, offset=offset, length=length
                ) as g:
            addr = self.segment * 0x10 + offset
            g.write(bytes(self._get_memory_block(addr, length)))
            # Tandys repeat the header at the end of the file
            if self._syntax == 'tandy':
                g.write(
                    devices.TYPE_TO_MAGIC[b'M'] + struct.pack('<HHH', self.segment, offset, length)
                )

    def def_seg_(self, args):
        """DEF SEG: Set segment."""
        segment, = args
        # &hb800: text screen buffer; &h13d: data segment
        if segment is None:
            self.segment = self._memory.data_segment
        else:
            # def_seg() accepts signed values
            self.segment = values.to_int(segment, unsigned=True)
            if self.segment < 0:
                self.segment += 0x10000

    def def_usr_(self, args):
        """DEF USR: Define machine language function."""
        usr, addr = args
        addr = values.to_integer(addr, unsigned=True)
        logging.warning('DEF USR statement not implemented')

    def call_(self, args):
        """CALL or CALLS: Call machine language procedure."""
        addr_var = next(args)
        # call procedure address must be numeric
        if self._memory.complete_name(addr_var)[-1:] == values.STR:
            # type mismatch
            raise error.BASICError(error.TYPE_MISMATCH)
        # ignore well-shaped arguments
        list(args)
        logging.warning('CALL/CALLS statement not implemented')

    ###########################################################################
    # IMPLEMENTATION

    def _get_memory(self, addr):
        """Retrieve the value at an emulated memory location."""
        try:
            # try if there's a preset value
            return self._peek_values[addr]
        except KeyError:
            if addr >= self.rom_segment*0x10:
                # ROM font
                return max(0, self._get_rom_memory(addr))
            elif addr >= self.ram_font_segment*0x10:
                # RAM font
                return max(0, self._get_font_memory(addr))
            elif addr >= self.video_segment*0x10:
                # graphics and text memory
                return max(0, self._get_video_memory(addr))
            elif addr >= self._memory.data_segment*0x10:
                return max(0, self._memory.get_memory(addr))
            elif addr >= 0:
                return max(0, self._get_low_memory(addr))
            else:
                return 0

    def _set_memory(self, addr, val):
        """Set the value at an emulated memory location."""
        if addr >= self.rom_segment*0x10:
            # ROM includes font memory
            pass
        elif addr >= self.ram_font_segment*0x10:
            # RAM font memory
            self._set_font_memory(addr, val)
        elif addr >= self.video_segment*0x10:
            # graphics and text memory
            self._set_video_memory(addr, val)
        elif addr >= self._memory.data_segment*0x10:
            self._memory.set_memory(addr, val)
        elif addr >= 0:
            self._set_low_memory(addr, val)

    def _get_memory_block(self, addr, length):
        """Retrieve a contiguous block of bytes from memory."""
        block = bytearray()
        if addr >= self.video_segment*0x10:
            video_len = 0x20000 - (addr - self.video_segment*0x10)
            # graphics and text memory - specialised call
            block += self._get_video_memory_block(addr, min(length, video_len))
            addr += video_len
            length -= video_len
        for a in range(addr, addr+length):
            block.append(max(0, self._get_memory(a)))
        return block

    def _set_memory_block(self, addr, buf):
        """Set a contiguous block of bytes in memory."""
        if addr >= self.video_segment*0x10:
            video_len = 0x20000 - (addr - self.video_segment*0x10)
            # graphics and text memory - specialised call
            self._set_video_memory_block(addr, buf[:video_len])
            addr += video_len
            buf = buf[video_len:]
        for a in range(len(buf)):
            self._set_memory(addr + a, buf[a])


    ###############################################################
    # video memory model

    def _get_video_memory(self, addr):
        """Retrieve a byte from video memory."""
        return self._display.mode.memorymap.get_memory(self._display, addr, 1)[0]

    def _set_video_memory(self, addr, val):
        """Set a byte in video memory."""
        with self._display.text_screen.collect_updates():
            self._display.mode.memorymap.set_memory(self._display, addr, [val])

    def _get_video_memory_block(self, addr, length):
        """Retrieve a contiguous block of bytes from video memory."""
        return bytearray(self._display.mode.memorymap.get_memory(self._display, addr, length))

    def _set_video_memory_block(self, addr, some_bytes):
        """Set a contiguous block of bytes in video memory."""
        with self._display.text_screen.collect_updates():
            self._display.mode.memorymap.set_memory(self._display, addr, some_bytes)

    ###############################################################################

    def _get_rom_memory(self, addr):
        """Retrieve data from ROM."""
        addr -= self.rom_segment*0x10
        if addr == 0xfffe:
            # machine ID byte
            # see http://stanislavs.org/helppc/id_bytes.html
            # FF	Original IBM PC  4/24/81
    		# FE	IBM XT (Original)
    		# FD	PCjr
    		# FC	IBM AT, XT 286, PS/1, PS/2 Model 50/60
    		# FB	IBM 256/640K XT (aka XT/2)
    		# FA	IBM PS/2 Model 30
    		# F9	IBM PC Convertible
    		# F8	IBM PS/2 Model 80/70
    		# B6    Hewlett Packard 110
    		# 9A	Compaq Plus
    		# 2D	Compaq PC
            # most clones including Tandy return FF (IBM PC) for compatibility
            # http://nerdlypleasures.blogspot.co.uk/2012/06/ibm-pcjr-and-tandy-1000-games.html
            if self._syntax == 'pcjr':
                return 0xfd
            return 0xff
        elif addr >= 0xe00e and addr < 0xe00e + 80:
            # version & copyright info instead of IBM BIOS copyright notice
            pos = addr - 0xe00e
            try:
                return NOTICE[pos]
            except IndexError:
                return -1
        else:
            # ROM font
            addr -= self.rom_font_addr
            char = addr // 8
            if char > 127 or char < 0:
                return -1
            return self.font_8.get_byte(char, addr%8)

    def _get_font_memory(self, addr):
        """Retrieve RAM font data."""
        addr -= self.ram_font_segment*0x10 + self.ram_font_addr
        char = addr // 8 + 128
        if char < 128 or char > 254:
            return -1
        return self.font_8.get_byte(char, addr%8)

    def _set_font_memory(self, addr, value):
        """Retrieve RAM font data."""
        addr -= self.ram_font_segment*0x10 + self.ram_font_addr
        char = addr // 8 + 128
        if char < 128 or char > 254:
            return
        self.font_8.set_byte(char, addr%8, value)

    #################################################################################


    def _get_low_memory(self, addr):
        """Retrieve data from low memory."""
        addr -= 0
        # from MEMORY.ABC: PEEKs and POKEs (Don Watkins)
        # http://www.qbasicnews.com/abc/showsnippet.php?filename=MEMORY.ABC&snippet=6
        # 108-115 control Ctrl-break capture; not implemented (see PC Mag POKEs)
        if addr == 124:
            return self.ram_font_addr % 256
        elif addr == 125:
            return self.ram_font_addr // 256
        elif addr == 126:
            return self.ram_font_segment % 256
        elif addr == 127:
            return self.ram_font_segment // 256
        # 1040 monitor type
        elif addr == 1040:
            if self._display.is_monochrome:
                # mono
                return 48 + 6
            else:
                # 80x25 graphics
                return 32 + 6
        # http://textfiles.com/programming/peekpoke.txt
        #   "(PEEK (1041) AND 14)/2" WILL PROVIDE NUMBER OF RS232 PORTS INSTALLED.
        #   "(PEEK (1041) AND 16)/16" WILL PROVIDE NUMBER OF GAME PORTS INSTALLED.
        #   "(PEEK (1041) AND 192)/64" WILL PROVIDE NUMBER OF PRINTERS INSTALLED.
        elif addr == 1041:
            return (
                2 * (
                    self._files.device_available(b'COM1:') +
                    self._files.device_available(b'COM2:')
                ) + 16 + 64 * (
                    self._files.device_available(b'LPT1:') +
                    self._files.device_available(b'LPT2:') +
                    self._files.device_available(b'LPT3:')
                )
            )
        # &h40:&h17 keyboard flag
        # &H80 - Insert state active
        # &H40 - CapsLock state has been toggled
        # &H20 - NumLock state has been toggled
        # &H10 - ScrollLock state has been toggled
        # &H08 - Alternate key depressed
        # &H04 - Control key depressed
        # &H02 - Left shift key depressed
        # &H01 - Right shift key depressed
        elif addr == 1047:
            return self.keyboard.mod
        # &h40:&h18 keyboard flag
        # &H80 - Insert key is depressed
        # &H40 - CapsLock key is depressed
        # &H20 - NumLock key is depressed
        # &H10 - ScrollLock key is depressed
        # &H08 - Suspend key has been toggled
        # not implemented: peek(1048)==4 if sysrq pressed, 0 otherwise
        elif addr == 1048:
            return 0
        elif addr == 1049:
            return int(self.keyboard.keypad_ascii or 0)%256
        elif addr == 1050:
            # keyboard ring buffer starts at n+1024; lowest 1054
            return (self.keyboard.buf.start*2 + self.key_buffer_offset) % 256
        elif addr == 1051:
            return (self.keyboard.buf.start*2 + self.key_buffer_offset) // 256
        elif addr == 1052:
            # ring buffer ends at n + 1023
            return (self.keyboard.buf.stop*2 + self.key_buffer_offset) % 256
        elif addr == 1053:
            return (self.keyboard.buf.stop*2 + self.key_buffer_offset) // 256
        elif addr in range(1024+self.key_buffer_offset, 1024+self.key_buffer_offset+32):
            index = (addr-1024-self.key_buffer_offset) // 2
            odd = (addr-1024-self.key_buffer_offset) % 2
            c, scan = self.keyboard.buf.ring_read(index)
            if odd:
                return scan or 0
            elif c == b'':
                return 0
            else:
                # however, arrow keys (all extended scancodes?) give 0xe0 instead of 0
                return ord(c[0:1])
        # 1097 screen mode number
        elif addr == 1097:
            # these are the low-level mode numbers used by mode switching interrupt
            return modes.get_mode_number(self._display.mode, self._display.colorswitch)
        # 1098, 1099 screen width
        elif addr == 1098:
            return self._display.mode.width % 256
        elif addr == 1099:
            return self._display.mode.width // 256
        # 1100, 1101 graphics page buffer size (32k for screen 9, 4k for screen 0)
        # 1102, 1103 zero (PCmag says graphics page buffer offset)
        elif addr == 1100:
            return self._display.mode.memorymap.page_size % 256
        elif addr == 1101:
            return self._display.mode.memorymap.page_size // 256
        # 1104 + 2*n (cursor column of page n) - 1
        # 1105 + 2*n (cursor row of page n) - 1
        # we only keep track of one row,col position
        elif addr in range(1104, 1120, 2):
            return self._display.text_screen.current_col - 1
        elif addr in range(1105, 1120, 2):
            return self._display.text_screen.current_row - 1
        # 1120, 1121 cursor shape
        elif addr == 1120:
            # to_line
            return self._display.cursor.shape[1]
        elif addr == 1121:
            # from_line
            return self._display.cursor.shape[0]
        # 1122 visual page number
        elif addr == 1122:
            return self._display.vpagenum
        # 1125 screen mode info
        elif addr == 1125:
            return self._display.get_mode_info_byte()
        # 1126 color
        elif addr == 1126:
            return self._display.get_colour_info_byte()
        # 1296, 1297: zero (PCmag says data segment address)
        return -1

    def _set_low_memory(self, addr, value):
        """Set data in low memory."""
        addr -= 0
        if addr == 1047:
            self.keyboard.mod = value
        # from basic_ref_3.pdf: the keyboard buffer may be cleared with
        # DEF SEG=0: POKE 1050, PEEK(1052)
        elif addr == 1050:
            # keyboard ring buffer starts at n+1024; lowest 1054
            self.keyboard.buf.ring_set_boundaries(
                (value - self.key_buffer_offset) // 2,
                self.keyboard.buf.stop
            )
        elif addr == 1052:
            # ring buffer ends at n + 1023
            self.keyboard.buf.ring_set_boundaries(
                self.keyboard.buf.start,
                (value - self.key_buffer_offset) // 2
            )
        elif addr in range(1024+self.key_buffer_offset, 1024+self.key_buffer_offset+32):
            index = (addr-1024-self.key_buffer_offset) // 2
            odd = (addr-1024-self.key_buffer_offset) % 2
            c, scan = self.keyboard.buf.ring_read(index)
            if odd:
                scan = value
            elif value in (0, 0xe0):
                c = b''
            else:
                c = int2byte(value)
            self.keyboard.buf.ring_write(index, c, scan)
