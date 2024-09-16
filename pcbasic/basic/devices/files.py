"""
PC-BASIC - files.py
Devices, Files and I/O operations

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
import inspect
import logging
import os
from typing import TYPE_CHECKING

from . import cassette
from . import devicebase
from . import disk
from . import formatter
from . import parports
from . import ports
from .. import values
from ..base import error
from ..base import tokens as tk
from ...compat import iterchar, iteritems, getcwdu
from ...compat import split_quoted
from ...compat import xrange, text_type

if TYPE_CHECKING:
    from ..console import Console
    from ..inputs import Keyboard

# MS-DOS device files
DOS_DEVICE_FILES = (b'AUX', b'CON', b'NUL', b'PRN')

# allowable drive letters in GW-BASIC are letters or @
DRIVE_LETTERS = b'@' + tk.UPPERCASE


############################################################################
# General file manipulation

class Files(object):
    """File manager."""

    def __init__(
            self, values, memory, queues, keyboard, display, console,
            max_files, max_reclen, serial_buffer_size,
            device_params, current_device,
            codepage, text_mode, soft_linefeed
        ):
        """Initialise files."""
        # for wait() in files_
        self._queues = queues
        self._values = values
        self._memory = memory
        self.files = {}
        self.max_files = max_files
        self.max_reclen = max_reclen
        self._init_devices(
            values, queues, display, console, keyboard,
            device_params, current_device,
            serial_buffer_size, codepage, text_mode, soft_linefeed
        )

    ###########################################################################
    # file management

    def close(self, num):
        """Close a numbered file."""
        try:
            self.files[num].close()
            del self.files[num]
        except KeyError:
            pass

    def close_all(self):
        """Close all files."""
        for f in self.files.values():
            f.close()
        self.files = {}

    async def open(
            self, number, description, filetype, mode=b'I', access=b'', lock=b'',
            reclen=128, seg=0, offset=0, length=0
        ):
        """Open a file on a device specified by description."""
        if (not description) or (number < 0) or (number > self.max_files):
            # bad file number; also for name='', for some reason
            raise error.BASICError(error.BAD_FILE_NUMBER)
        if number in self.files:
            raise error.BASICError(error.FILE_ALREADY_OPEN)
        mode = mode.upper()
        device, dev_param = self._get_device_param(description, mode)
        # get the field buffer
        field = self._memory.fields[number] if number else None
        # open the file on the device
        new_file = device.open(
            number, dev_param, filetype, mode, access, lock,
            reclen, seg, offset, length, field
        )
        if inspect.isawaitable(new_file):
            new_file = await new_file

        logging.debug(
            'Opened file %r as #%d (type %s, mode %s)', dev_param, number, filetype, mode
        )
        if number:
            self.files[number] = new_file
        return new_file

    def get(self, num, mode=b'IOAR', not_open=error.BAD_FILE_NUMBER):
        """Get the file object for a file number and check allowed mode."""
        if (num < 1):
            raise error.BASICError(error.BAD_FILE_NUMBER)
        try:
            the_file = self.files[num]
        except KeyError:
            raise error.BASICError(not_open)
        if the_file.mode.upper() not in mode:
            raise error.BASICError(error.BAD_FILE_MODE)
        return the_file

    def _get_from_integer(self, num, mode=b'IOAR'):
        """Get the file object for an Integer file number and check allowed mode."""
        num = values.to_int(num, unsigned=True)
        error.range_check(0, 255, num)
        return self.get(num, mode)

    ###########################################################################
    # device management

    def _init_devices(
            self, values, queues, display, console: 'Console', keyboard: 'Keyboard',
            device_params, current_device,
            serial_in_size, codepage, text_mode, soft_linefeed
        ):
        """Initialise devices."""
        device_params = self._normalise_params(device_params)
        # screen device, for files_()
        current_device = self._normalise_current_device(current_device, device_params)
        self._console = console
        self._keyboard = keyboard
        self._devices = {
            b'SCRN:': devicebase.SCRNDevice(display, console),
            # KYBD: device needs display as it can set the screen width
            b'KYBD:': devicebase.KYBDDevice(keyboard, display),
            # cassette: needs text screen to display Found and Skipped messages
            b'CAS1:': cassette.CASDevice(device_params.get(b'CAS1', None), self._console),
            # serial devices
            b'COM1:': ports.COMDevice(device_params.get(b'COM1', None), queues, serial_in_size),
            b'COM2:': ports.COMDevice(device_params.get(b'COM2', None), queues, serial_in_size),
            # parallel devices - LPT1: must always be available
            b'LPT1:': parports.LPTDevice(
                device_params.get(b'LPT1', None), devicebase.nullstream(), codepage
            ),
            b'LPT2:': parports.LPTDevice(device_params.get(b'LPT2', None), None, codepage),
            b'LPT3:': parports.LPTDevice(device_params.get(b'LPT3', None), None, codepage),
        }
        # device files
        self.scrn_file = self._devices[b'SCRN:'].device_file
        self.kybd_file = self._devices[b'KYBD:'].device_file
        self.lpt1_file = self._devices[b'LPT1:'].device_file
        # disks
        self._init_disk_devices(device_params, current_device, codepage, text_mode, soft_linefeed)

    def _normalise_current_device(self, current_device, device_params):
        """Normalise current device specification."""
        current_device = self._normalise_device_name(current_device)
        if current_device and current_device != b'CAS1' and current_device not in DRIVE_LETTERS:
            logging.error('Invalid current device `%s`', current_device)
            current_device = b''
        # no current device specified, or set to an undefined device
        if (
                not current_device
                or current_device not in device_params.keys()
                or not device_params[current_device]
            ):
            if b'Z' in device_params and device_params[b'Z']:
                # use z: if this is defined
                current_device = b'Z'
            else:
                # otherwise, set current device to last disk available
                # if nothing available, use the internal drive @
                available = sorted(
                    _k for _k in device_params.keys() if len(_k) == 1 and device_params[_k]
                )
                if available:
                    current_device = available[-1]
                else:
                    current_device = b'@'
        return current_device

    def _normalise_params(self, device_params):
        """Normalise keys in device parameter dict."""
        if not device_params:
            return {}
        output_dict = {}
        for key, value in iteritems(device_params):
            key = self._normalise_device_name(key)
            if not key:
                continue
            # convert value to unicode
            if isinstance(value, bytes):
                try:
                    value = value.decode('ascii')
                except UnicodeError:
                    logging.error(
                        'Invalid device parameter value: `%s` must be ascii if given as bytes.', key
                    )
                    continue
            output_dict[key] = value
        return output_dict

    def _normalise_device_name(self, key):
        """Normalise device name to uppercase ascii bytes without colon."""
        if not key:
            return b''
        if isinstance(key, text_type):
            try:
                key = key.encode('ascii')
            except UnicodeError:
                logging.error('Invalid device name: `%s` is not ascii.', key)
                return b''
        # strip off trailing : if provided
        if key.endswith(b':'):
            key = key[:-1]
        # convert to uppercase
        key = key.upper()
        return key

    def close_devices(self):
        """Close device master files."""
        for d in self._devices.values():
            d.close()

    def device_available(self, spec):
        """Return whether the device indicated by the spec (including :) is available."""
        dev_name = spec.split(b':', 1)[0] + b':'
        return (dev_name in self._devices) and self._devices[dev_name].available()

    def get_device(self, name):
        """Get a device by name (including :) or KeyError if not there."""
        return self._devices[name]

    def _get_device_param(self, file_spec, mode):
        """Get a device object and parameters from a file specification."""
        name = bytes(file_spec)
        split = name.split(b':', 1)
        if len(split) > 1:
            # colon (:) found
            dev_name = split[0].upper() + b':'
            dev_param = split[1]
            try:
                device = self._devices[dev_name]
            except KeyError:
                # not an allowable device or drive name
                # bad file number, for some reason
                raise error.BASICError(error.BAD_FILE_NUMBER)
        else:
            device = self._devices[self._current_device + b':']
            # MS-DOS device aliases - these can't be names of disk files
            if device != self._devices[b'CAS1:'] and name in DOS_DEVICE_FILES:
                if name == b'AUX':
                    device, dev_param = self._devices[b'COM1:'], b''
                elif name == b'CON' and mode == b'I':
                    device, dev_param = self._devices[b'KYBD:'], b''
                elif name == b'CON' and mode == b'O':
                    device, dev_param = self._devices[b'SCRN:'], b''
                elif name == b'PRN':
                    device, dev_param = self._devices[b'LPT1:'], b''
                elif name == b'NUL':
                    device, dev_param = devicebase.NullDevice(), b''
            else:
                # open file on default device
                dev_param = name
        return device, dev_param

    ###########################################################################
    # statement callbacks

    def reset_(self, args):
        """RESET: Close all files."""
        list(args)
        self.close_all()

    async def close_(self, args):
        """CLOSE: close a file, or all files."""
        at_least_one = False
        async for number in args:
            number = values.to_int(number)
            error.range_check(0, 255, number)
            at_least_one = True
            # close() deals with non-open numbers
            self.close(number)
        # if no file number given, close everything
        if not at_least_one:
            self.close_all()

    async def open_(self, args):
        """OPEN: open a data file."""
        first_expr = await values.next_string(args)
        if await anext(args):
            # old syntax
            mode = first_expr[:1].upper()
            if mode not in (b'I', b'O', b'A', b'R'):
                raise error.BASICError(error.BAD_FILE_MODE)
            number = values.to_int(await anext(args))
            error.range_check(0, 255, number)
            name = await values.next_string(args)
            access, lock = None, None
        else:
            # new syntax
            name = first_expr
            mode, access, lock = await anext(args), await anext(args), await anext(args)
            # AS file number clause
            number = values.to_int(await anext(args))
            error.range_check(0, 255, number)
        reclen = await anext(args)

        mode = mode or b'R'
        if reclen is None:
            reclen = 128
        else:
            reclen = values.to_int(reclen)
        # mode and access (if specified) must match if not a RANDOM file
        # If FOR APPEND ACCESS WRITE is specified, raises PATH/FILE ACCESS ERROR
        # If FOR and ACCESS mismatch in other ways, raises SYNTAX ERROR.
        if access:
            if mode == b'A' and access == b'W':
                raise error.BASICError(error.PATH_FILE_ACCESS_ERROR)
            elif ((mode == b'I' and access != b'R') or (mode == b'O' and access != b'W') or
                  (mode == b'A' and access != b'RW')):
                raise error.BASICError(error.STX)
        error.range_check(1, self.max_reclen, reclen)
        # can't open file 0, or beyond max_files
        error.range_check_err(1, self.max_files, number, error.BAD_FILE_NUMBER)
        await self.open(number, name, b'D', mode=mode, access=access, lock=lock, reclen=reclen)

    ###########################################################################

    async def field_(self, args):
        """FIELD: attach a variable to the record buffer."""
        number = values.to_int(await anext(args))
        error.range_check(0, 255, number)
        # check if file is open
        self.get(number, b'R')
        offset = 0
        try:
            while True:
                width = values.to_int(await anext(args))
                error.range_check(0, 255, width)
                name, index = await anext(args)
                name = self._memory.complete_name(name)
                self._memory.fields[number].attach_var(name, index, offset, width)
                offset += width
        except (StopIteration, StopAsyncIteration):
            pass

    def _check_pos(self, pos):
        """Helper function: PUT and GET syntax."""
        if pos is None:
            return pos
        # forcing to single before rounding - this means we don't have enough precision
        # to address each individual record close to the maximum record number
        # but that's in line with GW
        pos = int(round(values.to_single(pos).to_value()))
        # not 2^32-1 as the manual boasts!
        # pos-1 needs to fit in a single-precision mantissa
        error.range_check_err(1, 2 ** 25, pos, err=error.BAD_RECORD_NUMBER)
        return pos

    async def put_(self, args):
        """PUT: write record to file."""
        number = values.to_int(await anext(args))
        error.range_check(0, 255, number)
        the_file = self.get(number, b'R', not_open=error.BAD_FILE_MODE)
        pos = await anext(args)
        pos = self._check_pos(pos)
        the_file.put(pos)

    async def get_(self, args):
        """GET: read record from file."""
        number = values.to_int(await anext(args))
        error.range_check(0, 255, number)
        the_file = self.get(number, b'R', not_open=error.BAD_FILE_MODE)
        pos = await anext(args)
        pos = self._check_pos(pos)
        the_file.get(pos)

    ###########################################################################

    def _get_lock_limits(self, lock_start_rec, lock_stop_rec):
        """Get record lock limits."""
        if lock_start_rec is None and lock_stop_rec is None:
            return None, None
        if lock_start_rec is None:
            lock_start_rec = 1
        else:
            lock_start_rec = round(values.to_single(lock_start_rec).to_value())
        if lock_stop_rec is None:
            lock_stop_rec = lock_start_rec
        else:
            lock_stop_rec = round(values.to_single(lock_stop_rec).to_value())
        if lock_start_rec < 1 or lock_start_rec > 2 ** 25 - 2 or lock_stop_rec < 1 or lock_stop_rec > 2 ** 25 - 2:
            raise error.BASICError(error.BAD_RECORD_NUMBER)
        return lock_start_rec, lock_stop_rec

    async def lock_(self, args):
        """LOCK: set file or record locks."""
        num = values.to_int(await anext(args))
        error.range_check(0, 255, num)
        thefile = self.get(num)
        lock_start_rec, lock_stop_rec = await anext(args), await anext(args)
        try:
            thefile.lock(*self._get_lock_limits(lock_start_rec, lock_stop_rec))
        except AttributeError:
            # not a disk file
            raise error.BASICError(error.PERMISSION_DENIED)

    async def unlock_(self, args):
        """UNLOCK: set file or record locks."""
        num = values.to_int(await anext(args))
        error.range_check(0, 255, num)
        thefile = self.get(num)
        lock_start_rec, lock_stop_rec = await anext(args), await anext(args)
        try:
            thefile.unlock(*self._get_lock_limits(lock_start_rec, lock_stop_rec))
        except AttributeError:
            # not a disk file
            raise error.BASICError(error.PERMISSION_DENIED)

    ###########################################################################

    async def write_(self, args):
        """WRITE: Output machine-readable expressions to the screen or a file."""
        file_number = await anext(args)
        if file_number is None:
            output = self.scrn_file
        else:
            file_number = values.to_int(file_number)
            error.range_check(0, 255, file_number)
            output = self.get(file_number, b'OAR')
        outstrs = []
        try:
            while True:
                expr = await anext(args)
                if isinstance(expr, values.String):
                    outstrs.append(b'"%s"' % expr.to_str())
                else:
                    outstrs.append(values.to_repr(expr, leading_space=False, type_sign=False))
        except (StopIteration, StopAsyncIteration):
            # write the whole thing as one thing (this affects line breaks)
            await output.write_line(b','.join(outstrs))
        except error.BASICError:
            if outstrs:
                await output.write(b','.join(outstrs) + b',')
            raise

    async def width_(self, args):
        """WIDTH: set width of screen or device."""
        file_or_device = await anext(args)
        num_rows_dummy = None
        if file_or_device == tk.LPRINT:
            dev = self.lpt1_file
            w = values.to_int(await anext(args))
        elif isinstance(file_or_device, values.Number):
            file_or_device = values.to_int(file_or_device)
            error.range_check(0, 255, file_or_device)
            dev = self.get(file_or_device, mode=b'IOAR')
            w = values.to_int(await anext(args))
        else:
            expr = await anext(args)
            if isinstance(expr, values.String):
                devname = expr.to_str().upper()
                w = values.to_int(await anext(args))
                try:
                    dev = self._devices[devname].device_file
                except (KeyError, AttributeError):
                    # bad file name
                    raise error.BASICError(error.BAD_FILE_NAME)
            else:
                w = values.to_int(expr)
                num_rows_dummy = await anext(args)
                if num_rows_dummy is not None:
                    num_rows_dummy = values.to_int(num_rows_dummy)
                dev = self.scrn_file
        error.range_check(0, 255, w)
        [_ async for _ in args]
        if num_rows_dummy is not None:
            self.scrn_file._display.set_height(num_rows_dummy)
        dev.set_width(w)

    async def print_(self, args):
        """PRINT: Write expressions to the screen or a file."""
        # check for a file number
        file_number = await anext(args)
        if file_number is not None:
            file_number = values.to_int(file_number)
            error.range_check(0, 255, file_number)
            output = self.get(file_number, b'OAR')
            console = None
        else:
            # neither LPRINT not a file number: print to screen
            output = self.scrn_file
            console = self.scrn_file.console
        await formatter.Formatter(output, console).format(args)

    async def lprint_(self, args):
        """LPRINT: Write expressions to printer LPT1."""
        await formatter.Formatter(self.lpt1_file).format(args)

    ###########################################################################

    async def ioctl_statement_(self, args):
        """IOCTL: send control string to I/O device. Not implemented."""
        num = values.to_int(await anext(args))
        error.range_check(0, 255, num)
        thefile = self.get(num)
        control_string = await values.next_string(args)
        [_ async for _ in args]
        logging.warning('IOCTL statement not implemented.')
        raise error.BASICError(error.IFC)

    async def motor_(self, args):
        """MOTOR: drive cassette motor; not implemented."""
        logging.warning('MOTOR statement not implemented.')
        val = await anext(args)
        if val is not None:
            error.range_check(0, 255, values.to_int(val))
        # noinspection PyStatementEffect
        (e async for e in args)

    async def lcopy_(self, args):
        """LCOPY: screen copy / no-op in later GW-BASIC."""
        # See e.g. http://shadowsshot.ho.ua/docs001.htm#LCOPY
        val = await anext(args)
        if val is not None:
            error.range_check(0, 255, values.to_int(val))
        # noinspection PyStatementEffect
        (e async for e in args)

    ###########################################################################
    # function callbacks

    async def loc_(self, args):
        """LOC: get file pointer."""
        num = await anext(args)
        num = values.to_integer(num)
        loc = self._get_from_integer(num).loc()
        return self._values.new_single().from_int(loc)

    async def eof_(self, args):
        """EOF: get end-of-file."""
        num = await anext(args)
        num = values.to_integer(num)
        eof = self._values.new_integer()
        if not num.is_zero() and self._get_from_integer(num, b'IR').eof():
            eof = eof.from_int(-1)
        return eof

    async def lof_(self, args):
        """LOF: get length of file."""
        num = await anext(args)
        num = values.to_integer(num)
        lof = self._get_from_integer(num).lof()
        return self._values.new_single().from_int(lof)

    async def lpos_(self, args):
        """LPOS: get the current printer column."""
        num = await anext(args)
        num = values.to_int(num)
        error.range_check(0, 3, num)
        printer = self._devices[b'LPT%d:' % max(1, num)]
        col = printer.device_settings.col
        # follow weird GW-BASIC behaviour
        # this is reported as 1 if it equals the DEVICE's width plus one
        # even if it then continues until the FILE's width afterwards
        if printer.device_file and col == printer.device_file.width + 1:
            col = 1
        return self._values.new_integer().from_int(col % 256)

    async def input_(self, args):
        """INPUT$: read num chars from file or keyboard."""
        num = values.to_int(await anext(args))
        error.range_check(1, 255, num)
        filenum = await anext(args)
        if filenum is not None:
            filenum = values.to_int(filenum)
            error.range_check(0, 255, filenum)
            # raise BAD FILE MODE (not BAD FILE NUMBER) if the file is not open
            read = self.get(filenum, mode=b'IR', not_open=error.BAD_FILE_MODE).read
        else:
            read = self._keyboard.read_bytes_block
        [_ async for _ in args]
        # read the chars
        word = read(num)

        if inspect.isawaitable(word):
            word = await word

        if len(word) < num:
            # input past end
            raise error.BASICError(error.INPUT_PAST_END)
        return self._values.new_string().from_str(word)

    ###########################################################################

    async def ioctl_(self, args):
        """IOCTL$: read device control string response; not implemented."""
        num = values.to_int(await anext(args))
        error.range_check(0, 255, num)
        # raise BAD FILE NUMBER if the file is not open
        infile = self.get(num)
        # noinspection PyStatementEffect
        [_ async for _ in args]
        logging.warning('IOCTL$ function not implemented.')
        raise error.BASICError(error.IFC)

    def erdev_(self, args):
        """ERDEV: device error value; not implemented."""
        list(args)
        logging.warning('ERDEV function not implemented.')
        return self._values.new_integer()

    def erdev_str_(self, args):
        """ERDEV$: device error string; not implemented."""
        list(args)
        logging.warning('ERDEV$ function not implemented.')
        return self._values.new_string()

    async def exterr_(self, args):
        """EXTERR: device error information; not implemented."""
        val = await anext(args)
        logging.warning('EXTERR function not implemented.')
        error.range_check(0, 3, values.to_int(val))
        return self._values.new_integer()

    ###########################################################################
    # disk devices

    def _init_disk_devices(
            self, device_params, current_device,
            codepage, text_mode, soft_linefeed
    ):
        """Initialise disk devices."""
        # if Z not specified, mount to cwd by default (override by specifying 'Z': None)
        if b'Z' not in device_params:
            device_params[b'Z'] = getcwdu()
        # disk devices
        for letter in iterchar(DRIVE_LETTERS):
            if letter in device_params and device_params[letter]:
                # drive can be non-empty only on Windows, needs to be split out first as we use :
                drive, drivepath = os.path.splitdrive(device_params[letter])
                params = split_quoted(
                    drivepath, split_by=u':', quote=u'"', strip_quotes=True
                )
                path = drive + params[0]
                if len(params) > 1:
                    cwd = params[1]
                    # ignore any further specifiers
                else:
                    cwd = u''
            else:
                path, cwd = u'', u''
            # treat device @: separately - internal disk must exist but may remain unmounted
            disk_class = disk.InternalDiskDevice if letter == b'@' else disk.DiskDevice
            self._devices[letter + b':'] = disk_class(
                letter, path, cwd, codepage, text_mode, soft_linefeed
            )
        # current_device value is normalised
        self._current_device = current_device

    def _get_diskdevice_and_path(self, path):
        """Return the disk device and remaining path for given file spec."""
        # careful - do not convert path to uppercase, we still need to match
        splits = bytes(path).split(b':', 1)
        if len(splits) == 0:
            dev, spec = self._current_device, b''
        elif len(splits) == 1:
            dev, spec = self._current_device, splits[0]
        else:
            try:
                dev, spec = splits[0].upper(), splits[1]
            except KeyError:
                raise error.BASICError(error.DEVICE_UNAVAILABLE)
        # must be a disk device
        if dev not in DRIVE_LETTERS:
            raise error.BASICError(error.DEVICE_UNAVAILABLE)
        return self._devices[dev + b':'], spec

    def get_native_cwd(self):
        """Get current working directory on current drive."""
        # must be a disk device
        if self._current_device not in DRIVE_LETTERS:
            raise error.BASICError(error.IFC)
        return self._devices[self._current_device + b':'].get_native_cwd()

    async def chdir_(self, args):
        """CHDIR: change working directory."""
        name = await values.next_string(args)
        # noinspection PyStatementEffect
        [_ async for _ in args]
        if not name:
            raise error.BASICError(error.BAD_FILE_NAME)
        dev, path = self._get_diskdevice_and_path(name)
        dev.chdir(path)

    async def mkdir_(self, args):
        """MKDIR: create directory."""
        name = await values.next_string(args)
        # noinspection PyStatementEffect
        [_ async for _ in args]
        if not name:
            raise error.BASICError(error.BAD_FILE_NAME)
        dev, path = self._get_diskdevice_and_path(name)
        dev.mkdir(path)

    async def rmdir_(self, args):
        """RMDIR: remove directory."""
        name = await values.next_string(args)
        # noinspection PyStatementEffect
        [_ async for _ in args]
        if not name:
            raise error.BASICError(error.BAD_FILE_NAME)
        dev, path = self._get_diskdevice_and_path(name)
        dev.rmdir(path)

    async def name_(self, args):
        """NAME: rename file or directory."""
        dev, oldpath = self._get_diskdevice_and_path(await values.next_string(args))
        # don't rename open files
        # NOTE: we need to check file exists before parsing the next name
        # to get the same error sequencing as GW-BASIC
        dev.require_file_exists(oldpath)
        dev.require_file_not_open(oldpath)
        newdev, newpath = self._get_diskdevice_and_path(await values.next_string(args))
        dev.require_file_not_open(newpath)
        # noinspection PyStatementEffect
        [_ async for _ in args]
        if dev != newdev:
            raise error.BASICError(error.RENAME_ACROSS_DISKS)
        dev.rename(oldpath, newpath)

    async def kill_(self, args):
        """KILL: remove file."""
        name = await values.next_string(args)
        # noinspection PyStatementEffect
        [_ async for _ in args]
        if not name:
            raise error.BASICError(error.BAD_FILE_NAME)
        dev, path = self._get_diskdevice_and_path(name)
        dev.kill(path)

    async def files_(self, args):
        """FILES: output directory listing to screen."""
        pathmask = await values.next_string(args)
        # noinspection PyStatementEffect
        [_ async for _ in args]
        # pathmask may be left unspecified, but not empty
        if pathmask == b'':
            raise error.BASICError(error.BAD_FILE_NAME)
        elif pathmask is None:
            pathmask = b''
        dev, path = self._get_diskdevice_and_path(pathmask)
        # retrieve files first (to ensure correct path/file not found errors)
        output = dev.listdir(path)
        num_cols = self._console.width // 20
        # output working dir in DOS format
        # NOTE: this is always the current dir, not the one being listed
        await self._console.write_line(dev.get_cwd())
        if not output:
            raise error.BASICError(error.FILE_NOT_FOUND)
        # output files
        for i, cols in enumerate(output[j:j + num_cols] for j in xrange(0, len(output), num_cols)):
            await self._console.write_line(b' '.join(cols))
            if not (i % 4):
                # allow to break during dir listing & show names flowing on screen
                await self._queues.wait()
            i += 1
        await self._console.write_line(b' %d Bytes free\n' % dev.get_free())
