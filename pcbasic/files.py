"""
PC-BASIC - files.py
Devices, Files and I/O operations

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import error
import state
import devices

# MS-DOS device files
device_files = ('AUX', 'CON', 'NUL', 'PRN')

############################################################################
# General file manipulation

class Files(object):

    def __init__(self, max_files):
        """ Initialise files. """
        self.files = {}
        self.max_files = max_files

    def open(self, number, description, filetype, mode='I', access='R', lock='',
                  reclen=128, seg=0, offset=0, length=0):
        """ Open a file on a device specified by description. """
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
                device = state.io_state.devices[dev_name]
            except KeyError:
                # not an allowable device or drive name
                # bad file number, for some reason
                raise error.RunError(error.BAD_FILE_NUMBER)
        else:
            device = state.io_state.current_device
            # MS-DOS device aliases - these can't be names of disk files
            if device != state.io_state.devices['CAS1:'] and name in device_files:
                if name == 'AUX':
                    device, dev_param = state.io_state.devices['COM1:'], ''
                elif name == 'CON' and mode == 'I':
                    device, dev_param = state.io_state.devices['KYBD:'], ''
                elif name == 'CON' and mode == 'O':
                    device, dev_param = state.io_state.devices['SCRN:'], ''
                elif name == 'PRN':
                    device, dev_param = state.io_state.devices['LPT1:'], ''
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

    def get(self, num, mode='IOAR'):
        """ Get the file object for a file number and check allowed mode. """
        try:
            the_file = self.files[num]
        except KeyError:
            raise error.RunError(error.BAD_FILE_NUMBER)
        if the_file.mode.upper() not in mode:
            raise error.RunError(error.BAD_FILE_MODE)
        return the_file

    def close(self, num):
        """ Close a numbered file. """
        try:
            self.files[num].close()
            del self.files[num]
        except KeyError:
            pass

    def close_all(self):
        """ Close all files. """
        for f in self.files.values():
            f.close()
        self.files = {}
