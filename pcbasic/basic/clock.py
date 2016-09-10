"""
PC-BASIC - clock.py
Time and date utilities

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import datetime

from . import error


class Clock(object):

    def __init__(self):
        """Initialise clock."""
        # datetime offset for duration of the run
        # (so that we don't need permission to touch the system clock)
        # given in seconds
        self.time_offset = datetime.timedelta()

    def timer_(self):
        """TIMER: get clock ticks since midnight."""
        now = datetime.datetime.now() + self.time_offset
        midnight = datetime.datetime(now.year, now.month, now.day)
        diff = now-midnight
        seconds = diff.seconds
        micro = diff.microseconds
        ms = long(seconds)*1000 + long(micro)/1000
        # precision of GWBASIC TIMER is about 1/20 of a second
        return float(ms//50) / 20.

    def set_time(self, timestr):
        """Set the system time offset."""
        # allowed formats:  hh   hh:mm   hh:mm:ss  where hh 0-23, mm 0-59, ss 0-59
        now = datetime.datetime.now() + self.time_offset
        timelist = [0, 0, 0]
        pos, listpos, word = 0, 0, ''
        while pos < len(timestr):
            if listpos > 2:
                break
            c = timestr[pos]
            if c in (':', '.'):
                timelist[listpos] = int(word)
                listpos += 1
                word = ''
            elif (c < '0' or c > '9'):
                raise error.RunError(error.IFC)
            else:
                word += c
            pos += 1
        if word:
            timelist[listpos] = int(word)
        if timelist[0] > 23 or timelist[1] > 59 or timelist[2] > 59:
            raise error.RunError(error.IFC)
        newtime = datetime.datetime(now.year, now.month, now.day,
                    timelist[0], timelist[1], timelist[2], now.microsecond)
        self.time_offset += newtime - now

    def set_date(self, datestr):
        """Set the system date offset."""
        # allowed formats:
        # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
        # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
        now = datetime.datetime.now() + self.time_offset
        datelist = [1, 1, 1]
        pos, listpos, word = 0, 0, ''
        if len(datestr) < 8:
            raise error.RunError(error.IFC)
        while pos < len(datestr):
            if listpos > 2:
                break
            c = datestr[pos]
            if c in ('-', '/'):
                datelist[listpos] = int(word)
                listpos += 1
                word = ''
            elif (c < '0' or c > '9'):
                if listpos == 2:
                    break
                else:
                    raise error.RunError(error.IFC)
            else:
                word += c
            pos += 1
        if word:
            datelist[listpos] = int(word)
        if (datelist[0] > 12 or datelist[1] > 31 or
                (datelist[2] > 77 and datelist[2] < 80) or
                (datelist[2] > 99 and datelist[2] < 1980 or datelist[2] > 2099)):
            raise error.RunError(error.IFC)
        if datelist[2] <= 77:
            datelist[2] = 2000 + datelist[2]
        elif datelist[2] < 100 and datelist[2] > 79:
            datelist[2] = 1900 + datelist[2]
        try:
            newtime = datetime.datetime(
                            datelist[2], datelist[0], datelist[1],
                            now.hour, now.minute, now.second, now.microsecond)
        except ValueError:
            raise error.RunError(error.IFC)
        self.time_offset += newtime - now

    def time_fn_(self):
        """Get (offset) system time."""
        return bytearray((datetime.datetime.now() + self.time_offset)
                    .strftime('%H:%M:%S'))

    def date_fn_(self):
        """Get (offset) system date."""
        return bytearray((datetime.datetime.now() + self.time_offset)
                    .strftime('%m-%d-%Y'))
