"""
PC-BASIC - fp.py
MBF Floating-point arithmetic

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from . import fp
from . import error


class MathErrorHandler(object):
    """Handles floating point errors."""

    # types of errors that do not always interrupt execution
    soft_types = (OverflowError, ZeroDivisionError)

    def __init__(self, screen):
        """Setup handler."""
        self._screen = screen
        self._do_raise = False
        BaseMathErrorHandler.__init__(self)

    def pause_handling(self, do_raise):
        """Pause local handling of floating point errors."""
        self._do_raise = do_raise

    def wrap(self, e):
        """Handle Overflow or Division by Zero."""
        if isinstance(e, ValueError):
            # math domain errors such as SQR(-1)
            math_error = error.IFC
        elif isinstance(e, OverflowError):
            math_error = error.OVERFLOW
        elif isinstance(e, ZeroDivisionError):
            math_error = error.DIVISION_BY_ZERO
        else:
            raise e
        #if self.session.parser.on_error:
        if (self._do_raise or self._screen is None or
                math_error not in self.soft_types):
            # also raises exception in error_handle_mode!
            # in that case, prints a normal error message
            raise error.RunError(math_error)
        else:
            # write a message & continue as normal
            self._screen.write_line(error.RunError(math_error).message)
        # return max value for the appropriate float type
        if e.args and e.args[0] and isinstance(e.args[0], fp.Float):
            return fp.pack(e.args[0])
        return fp.pack(fp.Single.max.copy())
