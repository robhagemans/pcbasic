"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import io
import sys
import logging

from . import config
from . import info
from .basic import Session
from .debug import DebugSession
from .guard import ExceptionGuard
from .basic import NAME, VERSION, COPYRIGHT
from .interface import Interface, InitFailed
from .compat import stdio, resources, nullcontext
from .compat import script_entry_point_guard


async def main(*arguments):
    """Initialise, parse arguments and perform requested operations."""
    with config.TemporaryDirectory(prefix='pcbasic-') as temp_dir:
        # get settings and prepare logging
        settings = config.Settings(temp_dir, arguments)
        if settings.version:
            # print version and exit
            _show_version(settings)
        elif settings.help:
            # print usage and exit
            _show_usage()
        elif settings.convert:
            # convert and exit
            await _convert(settings)
        elif settings.interface:
            # start an interpreter session with interface
            await _run_session_with_interface(settings)
        else:
            # start an interpreter session with standard i/o
            await _run_session(**settings.launch_params)


def _show_usage():
    """Show usage description."""
    usage = resources.read_text(__package__ + '.' + 'data', 'USAGE.txt', errors='replace')
    stdio.stdout.write(usage)

def _show_version(settings):
    """Show version with optional debugging details."""
    if settings.debug:
        stdio.stdout.write(info.get_version_info())
        stdio.stdout.write(info.get_platform_info())
    else:
        stdio.stdout.write(u'%s %s\n%s\n' % (NAME, VERSION, COPYRIGHT))

async def _convert(settings):
    """Perform file format conversion."""
    mode, in_name, out_name = settings.conv_params
    with Session(**settings.session_params) as session:
        # binary stdin if no name supplied - use BytesIO buffer for seekability
        with session.bind_file(in_name or io.BytesIO(stdio.stdin.buffer.read())) as infile:
            await session.execute(b'LOAD "%s"' % (infile,))
        with session.bind_file(out_name or stdio.stdout.buffer, create=True) as outfile:
            mode_suffix = b',%s' % (mode.encode('ascii'),) if mode.upper() in ('A', 'P') else b''
            await session.execute(b'SAVE "%s"%s' % (outfile, mode_suffix))


async def _run_session_with_interface(settings):
    """Start an interactive interpreter session."""
    try:
        interface = Interface(**settings.iface_params)
    except InitFailed as e: # pragma: no cover
        logging.error(e)
    else:
        exception_guard = ExceptionGuard(interface, **settings.guard_params)
        await interface.launch(
            _run_session,
            interface=interface,
            exception_handler=exception_guard,
            **settings.launch_params
        )

async def _run_session(
        interface=None, exception_handler=nullcontext,
        resume=False, debug=False, state_file=None,
        prog=None, commands=(), keys=u'', greeting=True, **session_params
    ):
    """Start or resume session, handle exceptions, suspend on exit."""
    if resume:
        try:
            session: Session = Session.resume(state_file)
            session.add_pipes(**session_params)
        except Exception as e:
            # if we were told to resume but can't, give up
            logging.critical('Failed to resume session from %s: %s' % (state_file, e))
            sys.exit(1)
    elif debug:
        session = DebugSession(**session_params)
        exception_handler = nullcontext
    else:
        session = Session(**session_params)
    async with exception_handler(session) as handler:
        with session:
            try:
               await _operate_session(session, interface, prog, commands, keys, greeting)
            finally:
                try:
                    pass
                    # session.suspend(state_file)
                except Exception as e:
                    logging.error('Failed to save session to %s: %s', state_file, e)
    if exception_handler is not nullcontext and handler.exception_handled:
        await _run_session(
            interface, exception_handler, resume=True, state_file=state_file, greeting=False
        )


async def _operate_session(session: Session, interface, prog, commands, keys, greeting):
    """Run an interactive BASIC session."""
    session.attach(interface)
    if greeting:
        await session.greet()
    if prog:
        with session.bind_file(prog) as progfile:
            await session.execute(b'LOAD "%s"' % (progfile,))
    session.press_keys(keys)
    for cmd in commands:
        await session.execute(cmd)
    await session.interact()
