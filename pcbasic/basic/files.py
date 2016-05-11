"""
PC-BASIC - files.py
Devices, Files and I/O operations

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import string
import logging

from . import error
from . import devices
from . import cassette
from . import disk
from . import ports


# MS-DOS device files
device_files = ('AUX', 'CON', 'NUL', 'PRN')


############################################################################
# General file manipulation

class Files(object):
    """File manager."""

    def __init__(self, devices, max_files):
        """Initialise files."""
        self.files = {}
        self.max_files = max_files
        self.devices = devices

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

    def open(self, number, description, filetype, mode='I', access='R', lock='',
                  reclen=128, seg=0, offset=0, length=0):
        """Open a file on a device specified by description."""
        if (not description) or (number < 0) or (number > self.max_files):
            # bad file number; also for name='', for some reason
            raise error.RunError(error.BAD_FILE_NUMBER)
        if number in self.files:
            raise error.RunError(error.FILE_ALREADY_OPEN)
        name, mode = str(description), mode.upper()
        inst = None
        split_colon = name.split(':')
        if len(split_colon) > 1: # : found
            dev_name = split_colon[0].upper() + ':'
            dev_param = ''.join(split_colon[1:])
            try:
                device = self.devices.devices[dev_name]
            except KeyError:
                # not an allowable device or drive name
                # bad file number, for some reason
                raise error.RunError(error.BAD_FILE_NUMBER)
        else:
            device = self.devices.current_device
            # MS-DOS device aliases - these can't be names of disk files
            if device != self.devices.devices['CAS1:'] and name in device_files:
                if name == 'AUX':
                    device, dev_param = self.devices.devices['COM1:'], ''
                elif name == 'CON' and mode == 'I':
                    device, dev_param = self.devices.devices['KYBD:'], ''
                elif name == 'CON' and mode == 'O':
                    device, dev_param = self.devices.devices['SCRN:'], ''
                elif name == 'PRN':
                    device, dev_param = self.devices.devices['LPT1:'], ''
                elif name == 'NUL':
                    device, dev_param = devices.NullDevice(), ''
            else:
                # open file on default device
                dev_param = name
        # open the file on the device
        new_file = device.open(number, dev_param, filetype, mode, access, lock,
                               reclen, seg, offset, length)
        if number:
            self.files[number] = new_file
        return new_file

    def open_native_or_basic(self, infile):
        """If the specified file exists, open it; if not, try as BASIC file spec. Do not register in files dict."""
        try:
            # first try exact file name
            return self.devices.internal_disk.create_file_object(
                    open(os.path.expandvars(os.path.expanduser(infile)), 'rb'),
                    filetype='BPA', mode='I')
        except EnvironmentError as e:
            # otherwise, accept capitalised versions and default extension
            return self.open(0, infile, filetype='BPA', mode='I')

    def get(self, num, mode='IOAR'):
        """Get the file object for a file number and check allowed mode."""
        try:
            the_file = self.files[num]
        except KeyError:
            raise error.RunError(error.BAD_FILE_NUMBER)
        if the_file.mode.upper() not in mode:
            raise error.RunError(error.BAD_FILE_MODE)
        return the_file


###############################################################################
# device management

class Devices(object):
    """Device manager."""

    # allowable drive letters in GW-BASIC are letters or @
    drive_letters = b'@' + string.ascii_uppercase

    def __init__(self, session, fields, screen, keyboard,
                device_params, current_device, mount_dict,
                print_trigger, temp_dir, serial_in_size, utf8, universal):
        """Initialise devices."""
        self.devices = {}
        # screen device
        self.devices['SCRN:'] = devices.SCRNDevice(screen)
        # KYBD: device needs screen as it can set the screen width
        self.devices['KYBD:'] = devices.KYBDDevice(keyboard, screen)
        self.scrn_file = self.devices['SCRN:'].device_file
        self.kybd_file = self.devices['KYBD:'].device_file
        self.codepage = screen.codepage
        # ports
        # parallel devices - LPT1: must always be defined
        self.devices['LPT1:'] = ports.LPTDevice(device_params['LPT1:'], devices.nullstream(), print_trigger, self.codepage, temp_dir)
        self.devices['LPT2:'] = ports.LPTDevice(device_params['LPT2:'], None, print_trigger, self.codepage, temp_dir)
        self.devices['LPT3:'] = ports.LPTDevice(device_params['LPT3:'], None, print_trigger, self.codepage, temp_dir)
        self.lpt1_file = self.devices['LPT1:'].device_file
        # serial devices
        # buffer sizes (/c switch in GW-BASIC)
        self.devices['COM1:'] = ports.COMDevice(device_params['COM1:'], session, devices.Field(serial_in_size), serial_in_size)
        self.devices['COM2:'] = ports.COMDevice(device_params['COM2:'], session, devices.Field(serial_in_size), serial_in_size)
        # cassette
        # needs a screen for write() and write_line() to display Found and Skipped messages on opening files
        self.devices['CAS1:'] = cassette.CASDevice(device_params['CAS1:'], screen)
        # disk file locks
        self.locks = disk.Locks()
        # field buffers
        self.fields = fields
        # for wait() and check_events()
        self.session = session
        # text file settings
        self.utf8 = utf8
        self.universal = universal
        # disk devices
        self.internal_disk = disk.DiskDevice(b'', None, u'',
                        self.fields, self.locks, self.codepage, self.session, self.utf8, self.universal)
        for letter in self.drive_letters:
            if letter in mount_dict:
                self.devices[letter + b':'] = disk.DiskDevice(letter, mount_dict[letter][0], mount_dict[letter][1],
                            self.fields, self.locks, self.codepage, self.session, self.utf8, self.universal)
            else:
                self.devices[letter + b':'] = disk.DiskDevice(letter, None, u'',
                                self.fields, self.locks, self.codepage, self.session, self.utf8, self.universal)
        self.current_device = self.devices[current_device.upper() + b':']

    def resume(self, override_cas1, mount_dict, current_device):
        """Override settings after resume."""
        if override_cas1:
            self.devices['CAS1:'] = cassette.CASDevice(override_cas1, self.devices['CAS1:'].screen)
        for letter in mount_dict:
            self.devices[letter + b':'] = disk.DiskDevice(letter, mount_dict[letter][0], mount_dict[letter][1],
                        self.fields, self.locks, self.codepage, self.session, self.utf8, self.universal)
        # we always need to reset this or it may be a reference to an old device
        self.current_device = self.devices[current_device.upper() + b':']

    def close(self):
        """Close device master files."""
        for d in self.devices.values():
            d.close()

    def get_diskdevice_and_path(self, path):
        """Return the disk device and remaining path for given file spec."""
        # careful - do not convert path to uppercase, we still need to match
        splits = bytes(path).split(b':', 1)
        if len(splits) == 0:
            return self.current_device, b''
        elif len(splits) == 1:
            return self.current_device, splits[0]
        else:
            # must be a disk device
            if len(splits[0]) > 1:
                raise error.RunError(error.DEVICE_UNAVAILABLE)
            try:
                return self.devices[splits[0].upper() + b':'], splits[1]
            except KeyError:
                raise error.RunError(error.DEVICE_UNAVAILABLE)
