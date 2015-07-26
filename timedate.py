"""
PC-BASIC - timedate.py
Time and date utilities

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import datetime

import error
import state

# datetime offset for duration of the run (so that we don't need permission to touch the system clock)
# given in seconds
state.basic_state.time_offset = datetime.timedelta()


def timer_milliseconds():
    """ Get milliseconds since midnight. """
    now = datetime.datetime.now() + state.basic_state.time_offset
    midnight = datetime.datetime(now.year, now.month, now.day)
    diff = now-midnight
    seconds = diff.seconds
    micro = diff.microseconds
    return long(seconds)*1000 + long(micro)/1000

def set_time(timestr):
    """ Set the system time offset. """
    now = datetime.datetime.now() + state.basic_state.time_offset
    timelist = [0, 0, 0]
    pos, listpos, word = 0, 0, ''
    while pos < len(timestr):
        if listpos > 2:
            break
        c = chr(timestr[pos])
        if c in (':', '.'):
            timelist[listpos] = int(word)
            listpos += 1
            word = ''
        elif (c < '0' or c > '9'):
            raise error.RunError(5)
        else:
            word += c
        pos += 1
    if word:
        timelist[listpos] = int(word)
    if timelist[0] > 23 or timelist[1] > 59 or timelist[2] > 59:
        raise error.RunError(5)
    newtime = datetime.datetime(now.year, now.month, now.day, timelist[0], timelist[1], timelist[2], now.microsecond)
    state.basic_state.time_offset += newtime - now

def set_date(datestr):
    """ Set the system date offset. """
    now = datetime.datetime.now() + state.basic_state.time_offset
    datelist = [1, 1, 1]
    pos, listpos, word = 0, 0, ''
    if len(datestr) < 8:
        raise error.RunError(5)
    while pos < len(datestr):
        if listpos > 2:
            break
        c = chr(datestr[pos])
        if c in ('-', '/'):
            datelist[listpos] = int(word)
            listpos += 1
            word = ''
        elif (c < '0' or c > '9'):
            if listpos == 2:
                break
            else:
                raise error.RunError(5)
        else:
            word += c
        pos += 1
    if word:
        datelist[listpos] = int(word)
    if (datelist[0] > 12 or datelist[1] > 31 or
            (datelist[2] > 77 and datelist[2] < 80) or
            (datelist[2] > 99 and datelist[2] < 1980 or datelist[2] > 2099)):
        raise error.RunError(5)
    if datelist[2] <= 77:
        datelist[2] = 2000 + datelist[2]
    elif datelist[2] < 100 and datelist[2] > 79:
        datelist[2] = 1900 + datelist[2]
    try:
        newtime = datetime.datetime(datelist[2], datelist[0], datelist[1], now.hour, now.minute, now.second, now.microsecond)
    except ValueError:
        raise error.RunError(5)
    state.basic_state.time_offset += newtime - now

def get_time():
    """ Get (offset) system time. """
    return bytearray((datetime.datetime.now() + state.basic_state.time_offset).strftime('%H:%M:%S'))

def get_date():
    """ Get (offset) system date. """
    return bytearray((datetime.datetime.now() + state.basic_state.time_offset).strftime('%m-%d-%Y'))
