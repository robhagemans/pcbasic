Debugging Basic with the Python Debugger
========================================

You can debug a Basic program using python's built-in debugger ``pdb``.
Start the pcbasic interpreter in the python debugger::

    python3 -m pdb /path/to/pcbasic your-program.bas --interface=none -d

Alternatively you may want to use the native interface to not interfere
with the debugger. Or you may want to specify the ``--input`` option to
make pcbasic read from a file instead of the console.

Of course you want to be familiar with the python debugger which has
excellent `documentation`_

.. _`documentation`: https://docs.python.org/3/library/pdb.html

Stopping at a Basic line number
-------------------------------

In pcbasic in the file ``interpreter.py`` around line 105 there is a line
reading::

    if self.tron:

This line checks if the Basic interpreter built-in trace facility is
active and at this point the line number of the basic program is known.
So we can set a breakpoint in the python debugger there::

    break /usr/lib/python3/dist-packages/pcbasic/basic/interpreter.py:105

As said before, your version of pcbasic may need a different line number
if the statment above has changed position.

Now you can single-step through your Basic program with the pdb command
``continue`` abbreviated ``c``.
You can display the current Basic line number using::

    p struct.unpack_from('<H', token, 2)[0]

and we can print the line number every time the breakpoint is hit::

    commands 1
    p struct.unpack_from('<H', token, 2)[0]
    end

The ``commands 1`` instructs the debugger to associate the following
commands (until a line with only ``end``) with the breakpoint numbered 1.

To run the basic program until a specific line number is reached, we can
put a condition on the breakpoint::

    condition 1 struct.unpack_from('<H', token, 2)[0] == 42

When you enter ``c`` after this command, the program will be run until
it has reached line number 42 and stop before executing that line.

To make the breakpoint unconditional again (so we can single-step
through our program) enter::

    condition 1

Inspecting variables
--------------------

You can display a scalar variable using::

    p self._scalars.get (b'U2!').to_value()

Note that variables are stored with their sigil, see the `the
documentation on sigils`_ for details. The example above is the single
precision floating point variable ``U2!``.

.. _`the documentation on sigils`:
    http://robhagemans.github.io/pcbasic/doc/2.0/#typechars

This extends to arrays::

    p self._memory.arrays.get(b'J2!', [1,1]).to_value()

will list the item at position 1,1 in the two-dimensional array ``J2!``.
You can display a complete array using::

    p self._memory.arrays.to_list (b'J2!')

At the time of this writing the ``to_list`` method has a bug that does
not display the last item in every dimension, there is a `bug report`_
you may want to check.

.. _`bug report`: https://github.com/robhagemans/pcbasic/issues/182

You can check the dimension of an array with::

    p self._memory.arrays.dimensions (b'J2!')

Or display a sorted list of all defined scalar variables::

    p sorted (self._scalars._vars.keys())

These are the basics for getting started, of course you may use other
features of the debugger and/or the pcbasic interpreter for debugging
your programs.
