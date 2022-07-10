"""
PC-BASIC - clock.py
Time and date utilities

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import datetime

from .base import error
from . import values


class Clock(object):

    def __init__(self, values):
        """Initialise clock."""
        # datetime offset for duration of the run
        # (so that we don't need permission to touch the system clock)
        # given in seconds
        self._values = values
        self.time_offset = datetime.timedelta()

    def get_time_ms(self):
        """Get milliseconds since midnight."""
        now = datetime.datetime.now() + self.time_offset
        midnight = datetime.datetime(now.year, now.month, now.day)
        diff = now-midnight
        seconds = diff.seconds
        micro = diff.microseconds
        return int(seconds*1000 + micro/1000)

    def timer_(self, args):
        """TIMER: get clock ticks since midnight."""
        list(args)
        # precision of GWBASIC TIMER is about 1/20 of a second
        timer = float(self.get_time_ms()//50) / 20.
        return self._values.new_single().from_value(timer)

    def time_(self, args):
        """TIME: Set the system time offset."""
        timestr = values.next_string(args)
        list(args)
        # allowed formats:  hh   hh:mm   hh:mm:ss  where hh 0-23, mm 0-59, ss 0-59
        now = datetime.datetime.now() + self.time_offset
        strlist = timestr.replace(b'.', b':').split(b':')
        if len(strlist) == 1:
            strlist = strlist[0].split(b'.')
        if len(strlist) not in (1, 2, 3):
            raise error.BASICError(error.IFC)
        try:
            timelist = [int(s) for s in strlist]
        except ValueError:
            raise error.BASICError(error.IFC)
        timelist += [0] * (3 - len(timelist))
        if timelist[0] > 23 or timelist[1] > 59 or timelist[2] > 59:
            raise error.BASICError(error.IFC)
        newtime = datetime.datetime(now.year, now.month, now.day,
                    timelist[0], timelist[1], timelist[2], now.microsecond)
        self.time_offset += newtime - now

    def date_(self, args):
        """DATE: Set the system date offset."""
        datestr = values.next_string(args)
        # allowed formats:
        # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
        # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
        now = datetime.datetime.now() + self.time_offset
        strlist = datestr.replace(b'/', b'-').split(b'-')
        if len(strlist) != 3:
            raise error.BASICError(error.IFC)
        try:
            datelist = [int(s) for s in strlist]
        except ValueError:
            raise error.BASICError(error.IFC)
        if (
                datelist[0] > 12 or datelist[1] > 31 or
                (datelist[2] > 77 and datelist[2] < 80) or
                (datelist[2] > 99 and datelist[2] < 1980 or datelist[2] > 2099)
            ):
            raise error.BASICError(error.IFC)
        if datelist[2] <= 77:
            datelist[2] = 2000 + datelist[2]
        elif datelist[2] < 100 and datelist[2] > 79:
            datelist[2] = 1900 + datelist[2]
        try:
            newtime = datetime.datetime(
                datelist[2], datelist[0], datelist[1],
                now.hour, now.minute, now.second, now.microsecond
            )
        except ValueError:
            raise error.BASICError(error.IFC)
        list(args)
        self.time_offset += newtime - now

    def time_fn_(self, args):
        """Get (offset) system time."""
        list(args)
        time = (datetime.datetime.now() + self.time_offset).strftime('%H:%M:%S')
        return self._values.new_string().from_str(time.encode('ascii'))

    def date_fn_(self, args):
        """Get (offset) system date."""
        list(args)
        date = (datetime.datetime.now() + self.time_offset).strftime('%m-%d-%Y')
        return self._values.new_string().from_str(date.encode('ascii'))
