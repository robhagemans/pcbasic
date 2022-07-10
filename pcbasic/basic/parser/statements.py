"""
PC-BASIC - statements.py
Statement parser

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import struct
from functools import partial

from ...compat import iterchar
from ..base import error
from ..base import tokens as tk
from ..base.tokens import DIGITS, LETTERS
from .. import values
from . import expressions
from . import userfunctions


class Parser(object):
    """BASIC statement parser."""

    def __init__(self, values, memory, syntax):
        """Initialise statement context."""
        # re-execute current statement after Break
        self.redo_on_break = False
        # expression parser
        self.expression_parser = expressions.ExpressionParser(values, memory)
        self.user_functions = self.expression_parser.user_functions
        # syntax: advanced, pcjr, tandy
        self._syntax = syntax
        # initialise syntax parser tables
        self._init_syntax()

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # can't be pickled
        pickle_dict['_simple'] = None
        pickle_dict['_complex'] = None
        pickle_dict['_callbacks'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)
        self._init_syntax()

    def init_callbacks(self, session):
        """Assign statement and function callbacks."""
        self.init_statements(session)
        self.expression_parser.init_functions(session)

    def parse_statement(self, ins):
        """Parse and execute a single statement."""
        # read keyword token or one byte
        ins.skip_blank()
        c = ins.read_keyword_token()
        if c in self._simple:
            parse_args = self._simple[c]
        elif c in self._complex:
            stat_dict = self._complex[c]
            ins.skip_blank()
            selector = ins.read_keyword_token()
            ins.seek(-len(selector), 1)
            if selector not in stat_dict.keys():
                selector = None
            else:
                c += selector
            parse_args = stat_dict[selector]
        else:
            ins.seek(-len(c), 1)
            if c in set(iterchar(LETTERS)):
                # implicit LET
                c = tk.LET
                parse_args = self._simple[tk.LET]
            else:
                ins.require_end()
                return
        self._callbacks[c](parse_args(ins))
        # end-of-statement is checked at start of next statement in interpreter loop

    def parse_name(self, ins):
        """Get scalar part of variable name from token stream."""
        name = ins.read_name()
        # must not be empty
        error.throw_if(not name, error.STX)
        # append sigil, if missing
        return name

    def parse_expression(self, ins, allow_empty=False):
        """Compute the value of the expression at the current code pointer."""
        if allow_empty and ins.skip_blank() in tk.END_EXPRESSION:
            return None
        self.redo_on_break = True
        val = self.expression_parser.parse_expression(ins)
        self.redo_on_break = False
        return val

    ###########################################################################

    def _init_syntax(self):
        """Initialise syntax parsers."""
        self._simple = {
            tk.DATA: self._skip_statement,
            tk.COMMON: self._skip_statement,
            tk.REM: self._skip_line,
            tk.ELSE: self._skip_line,
            tk.CONT: self._parse_nothing,
            tk.TRON: self._parse_nothing,
            tk.TROFF: self._parse_nothing,
            tk.WHILE: self._parse_nothing,
            tk.RESET: self._parse_end,
            tk.END: self._parse_end,
            tk.STOP: self._parse_end,
            tk.NEW: self._parse_end,
            tk.WEND: self._parse_end,
            tk.SYSTEM: self._parse_end,
            tk.FOR: self._parse_for,
            tk.NEXT: self._parse_next,
            tk.INPUT: self._parse_input,
            tk.DIM: self._parse_var_list,
            tk.READ: self._parse_var_list,
            tk.LET: self._parse_let,
            tk.GOTO: self._parse_single_line_number,
            tk.RUN: self._parse_run,
            tk.IF: self._parse_if,
            tk.RESTORE: self._parse_restore,
            tk.GOSUB: self._parse_single_line_number,
            tk.RETURN: self._parse_optional_line_number,
            tk.PRINT: partial(self._parse_print, parse_file=True),
            tk.CLEAR: self._parse_clear,
            tk.LIST: self._parse_list,
            tk.WAIT: self._parse_wait,
            tk.POKE: self._parse_two_args,
            tk.OUT: self._parse_two_args,
            tk.LPRINT: partial(self._parse_print, parse_file=False),
            tk.LLIST: self._parse_delete_llist,
            tk.WIDTH: self._parse_width,
            tk.SWAP: self._parse_swap,
            tk.ERASE: self._parse_erase,
            tk.EDIT: self._parse_edit,
            tk.ERROR: self._parse_single_arg,
            tk.RESUME: self._parse_resume,
            tk.DELETE: self._parse_delete_llist,
            tk.AUTO: self._parse_auto,
            tk.RENUM: self._parse_renum,
            tk.DEFSTR: self._parse_deftype,
            tk.DEFINT: self._parse_deftype,
            tk.DEFSNG: self._parse_deftype,
            tk.DEFDBL: self._parse_deftype,
            tk.CALL: self._parse_call,
            tk.CALLS: self._parse_call,
            tk.WRITE: self._parse_write,
            tk.OPTION: self._parse_option_base,
            tk.RANDOMIZE: self._parse_optional_arg,
            tk.OPEN: self._parse_open,
            tk.CLOSE: self._parse_close,
            tk.LOAD: self._parse_load,
            tk.MERGE: self._parse_single_arg_no_end,
            tk.SAVE: self._parse_save,
            tk.COLOR: self._parse_color,
            tk.CLS: self._parse_cls,
            tk.MOTOR: self._parse_optional_arg,
            tk.BSAVE: self._parse_bsave,
            tk.BLOAD: self._parse_bload,
            tk.SOUND: self._parse_sound,
            tk.BEEP: self._parse_beep,
            tk.PSET: self._parse_pset_preset,
            tk.PRESET: self._parse_pset_preset,
            tk.SCREEN: self._parse_screen,
            tk.LOCATE: self._parse_locate,
            tk.FILES: self._parse_optional_arg_no_end,
            tk.FIELD: self._parse_field,
            tk.NAME: self._parse_name,
            tk.LSET: self._parse_let,
            tk.RSET: self._parse_let,
            tk.KILL: self._parse_single_arg_no_end,
            tk.CHAIN: self._parse_chain,
            tk.DATE: self._parse_time_date,
            tk.TIME: self._parse_time_date,
            tk.PAINT: self._parse_paint,
            tk.COM: self._parse_com_command,
            tk.CIRCLE: self._parse_circle,
            tk.DRAW: self._parse_single_arg,
            tk.TIMER: self._parse_event_command,
            tk.IOCTL: self._parse_ioctl,
            tk.CHDIR: self._parse_single_arg_no_end,
            tk.MKDIR: self._parse_single_arg_no_end,
            tk.RMDIR: self._parse_single_arg_no_end,
            tk.SHELL: self._parse_optional_arg_no_end,
            tk.ENVIRON: self._parse_single_arg_no_end,
            tk.WINDOW: self._parse_window,
            tk.LCOPY: self._parse_optional_arg,
            tk.PCOPY: self._parse_pcopy,
            tk.LOCK: self._parse_lock_unlock,
            tk.UNLOCK: self._parse_lock_unlock,
            tk.MID: self._parse_mid,
            tk.PEN: self._parse_event_command,
            b'_': self._parse_call_extension,
        }
        if self._syntax in ('pcjr', 'tandy'):
            self._simple.update({
                tk.TERM: self._parse_end,
                tk.NOISE: self._parse_noise,
            })
        self._complex = {
            tk.ON: {
                tk.ERROR: self._parse_on_error_goto,
                tk.KEY: self._parse_on_event,
                tk.PEN: self._parse_on_event,
                tk.TIMER: self._parse_on_event,
                tk.PLAY: self._parse_on_event,
                tk.COM: self._parse_on_event,
                tk.STRIG: self._parse_on_event,
                None: self._parse_on_jump,
            },
            tk.DEF: {
                tk.FN: self._parse_def_fn,
                tk.USR: self._parse_def_usr,
                None: self._parse_def_seg,
            },
            tk.LINE: {
                tk.INPUT: self._parse_line_input,
                None: self._parse_line,
            },
            tk.KEY: {
                tk.ON: self._parse_key_macro,
                tk.OFF: self._parse_key_macro,
                tk.LIST: self._parse_key_macro,
                b'(': self._parse_com_command,
                None: self._parse_two_args,
            },
            tk.PUT: {
                b'(': self._parse_put_graph,
                None: self._parse_put_get_file,
            },
            tk.GET: {
                b'(': self._parse_get_graph,
                None: self._parse_put_get_file,
            },
            tk.PLAY: {
                tk.ON: self._parse_event_command,
                tk.OFF: self._parse_event_command,
                tk.STOP: self._parse_event_command,
                None: self._parse_play,
            },
            tk.VIEW: {
                tk.PRINT: self._parse_view_print,
                None: self._parse_view,
            },
            tk.PALETTE: {
                tk.USING: self._parse_palette_using,
                None: self._parse_palette,
            },
            tk.STRIG: {
                tk.ON: self._parse_strig_switch,
                tk.OFF: self._parse_strig_switch,
                None: self._parse_com_command,
            },
        }

    def init_statements(self, session):
        """Initialise statement callbacks."""
        self._callbacks = {
            tk.DATA: list,
            tk.COMMON: list,
            tk.REM: list,
            tk.ELSE: list,
            tk.CONT: session.interpreter.cont_,
            tk.TRON: session.interpreter.tron_,
            tk.TROFF: session.interpreter.troff_,
            tk.WHILE: session.interpreter.while_,
            tk.RESET: session.files.reset_,
            tk.END: session.end_,
            tk.STOP: session.interpreter.stop_,
            tk.NEW: session.new_,
            tk.WEND: session.interpreter.wend_,
            tk.SYSTEM: session.system_,
            tk.FOR: session.interpreter.for_,
            tk.NEXT: session.interpreter.next_,
            tk.INPUT: session.input_,
            tk.DIM: session.memory.arrays.dim_,
            tk.READ: session.interpreter.read_,
            tk.LET: session.memory.let_,
            tk.GOTO: session.interpreter.goto_,
            tk.RUN: session.run_,
            tk.IF: session.interpreter.if_,
            tk.RESTORE: session.interpreter.restore_,
            tk.GOSUB: session.interpreter.gosub_,
            tk.RETURN: session.interpreter.return_,
            tk.PRINT: session.files.print_,
            tk.CLEAR: session.clear_,
            tk.LIST: session.list_,
            tk.WAIT: session.machine.wait_,
            tk.POKE: session.all_memory.poke_,
            tk.OUT: session.machine.out_,
            tk.LPRINT: session.files.lprint_,
            tk.LLIST: session.interpreter.llist_,
            tk.WIDTH: session.files.width_,
            tk.SWAP: session.memory.swap_,
            tk.ERASE: session.memory.arrays.erase_,
            tk.EDIT: session.edit_,
            tk.ERROR: session.interpreter.error_,
            tk.RESUME: session.interpreter.resume_,
            tk.DELETE: session.delete_,
            tk.AUTO: session.auto_,
            tk.RENUM: session.interpreter.renum_,
            tk.DEFSTR: session.memory.defstr_,
            tk.DEFINT: session.memory.defint_,
            tk.DEFSNG: session.memory.defsng_,
            tk.DEFDBL: session.memory.defdbl_,
            tk.CALL: session.all_memory.call_,
            tk.CALLS: session.all_memory.call_,
            tk.WRITE: session.files.write_,
            tk.OPTION: session.memory.arrays.option_base_,
            tk.RANDOMIZE: session.randomize_,
            tk.OPEN: session.files.open_,
            tk.CLOSE: session.files.close_,
            tk.LOAD: session.load_,
            tk.MERGE: session.merge_,
            tk.SAVE: session.save_,
            tk.COLOR: session.display.color_,
            tk.CLS: session.display.cls_,
            tk.MOTOR: session.files.motor_,
            tk.BSAVE: session.all_memory.bsave_,
            tk.BLOAD: session.all_memory.bload_,
            tk.SOUND: session.sound.sound_,
            tk.BEEP: session.sound.beep_,
            tk.PSET: session.graphics.pset_,
            tk.PRESET: session.graphics.preset_,
            tk.SCREEN: session.display.screen_,
            tk.LOCATE: session.text_screen.locate_,
            tk.FILES: session.files.files_,
            tk.FIELD: session.files.field_,
            tk.NAME: session.files.name_,
            tk.LSET: session.memory.lset_,
            tk.RSET: session.memory.rset_,
            tk.KILL: session.files.kill_,
            tk.CHAIN: session.chain_,
            tk.DATE: session.clock.date_,
            tk.TIME: session.clock.time_,
            tk.PAINT: session.graphics.paint_,
            tk.COM: session.basic_events.com_,
            tk.CIRCLE: session.graphics.circle_,
            tk.DRAW: session.graphics.draw_,
            tk.TIMER: session.basic_events.timer_,
            tk.IOCTL: session.files.ioctl_statement_,
            tk.CHDIR: session.files.chdir_,
            tk.MKDIR: session.files.mkdir_,
            tk.RMDIR: session.files.rmdir_,
            tk.SHELL: session.shell_,
            tk.ENVIRON: session.environment.environ_statement_,
            tk.WINDOW: session.graphics.window_,
            tk.LCOPY: session.files.lcopy_,
            tk.PCOPY: session.display.pcopy_,
            tk.LOCK: session.files.lock_,
            tk.UNLOCK: session.files.unlock_,
            tk.MID: session.memory.mid_,
            tk.PEN: session.basic_events.pen_,
            tk.TERM: session.term_,
            tk.NOISE: session.sound.noise_,
            tk.ON + tk.ERROR: session.interpreter.on_error_goto_,
            tk.ON + tk.KEY: session.basic_events.on_event_gosub_,
            tk.ON + tk.PEN: session.basic_events.on_event_gosub_,
            tk.ON + tk.TIMER: session.basic_events.on_event_gosub_,
            tk.ON + tk.PLAY: session.basic_events.on_event_gosub_,
            tk.ON + tk.COM: session.basic_events.on_event_gosub_,
            tk.ON + tk.STRIG: session.basic_events.on_event_gosub_,
            tk.ON: session.interpreter.on_jump_,
            tk.DEF + tk.FN: session.interpreter.def_fn_,
            tk.DEF + tk.USR: session.all_memory.def_usr_,
            tk.DEF: session.all_memory.def_seg_,
            tk.LINE + tk.INPUT: session.line_input_,
            tk.LINE: session.graphics.line_,
            tk.KEY + tk.ON: session.console.key_,
            tk.KEY + tk.OFF: session.console.key_,
            tk.KEY + tk.LIST: session.console.key_,
            tk.KEY + b'(': session.basic_events.key_,
            tk.KEY: session.key_,
            tk.PUT + b'(': session.graphics.put_,
            tk.PUT: session.files.put_,
            tk.GET + b'(': session.graphics.get_,
            tk.GET: session.files.get_,
            tk.PLAY + tk.ON: session.basic_events.play_,
            tk.PLAY + tk.OFF: session.basic_events.play_,
            tk.PLAY + tk.STOP: session.basic_events.play_,
            tk.PLAY: session.sound.play_,
            tk.VIEW + tk.PRINT: session.text_screen.view_print_,
            tk.VIEW: session.graphics.view_,
            tk.PALETTE + tk.USING: session.display.palette_using_,
            tk.PALETTE: session.display.palette_,
            tk.STRIG + tk.ON: session.stick.strig_statement_,
            tk.STRIG + tk.OFF: session.stick.strig_statement_,
            tk.STRIG: session.basic_events.strig_,
            b'_': session.extensions.call_as_statement,
        }

    ###########################################################################
    # auxiliary functions

    def _parse_bracket(self, ins):
        """Compute the value of the bracketed expression."""
        ins.require_read((b'(',))
        # we'll get a Syntax error, not a Missing operand, if we close with )
        val = self.parse_expression(ins)
        ins.require_read((b')',))
        return val

    def _parse_variable(self, ins):
        """Helper function: parse a scalar or array element."""
        name = ins.read_name()
        error.throw_if(not name, error.STX)
        self.redo_on_break = True
        indices = self.expression_parser.parse_indices(ins)
        self.redo_on_break = False
        return name, indices

    def _parse_jumpnum(self, ins):
        """Parses a line number pointer as in GOTO, GOSUB, LIST, RENUM, EDIT, etc."""
        ins.require_read((tk.T_UINT,))
        token = ins.read(2)
        assert len(token) == 2, 'Bytecode truncated in line number pointer'
        return struct.unpack('<H', token)[0]

    def _parse_optional_jumpnum(self, ins):
        """Parses a line number pointer as in GOTO, GOSUB, LIST, RENUM, EDIT, etc."""
        # no line number
        if ins.skip_blank() != tk.T_UINT:
            return None
        return self._parse_jumpnum(ins)

    def _parse_line_range(self, ins):
        """Parse a line number range as in LIST, DELETE."""
        from_line = self._parse_jumpnum_or_dot(ins, allow_empty=True)
        if ins.skip_blank_read_if((tk.O_MINUS,)):
            to_line = self._parse_jumpnum_or_dot(ins, allow_empty=True)
        else:
            to_line = from_line
        return (from_line, to_line)

    def _parse_jumpnum_or_dot(self, ins, allow_empty=False, err=error.STX):
        """Parse jump target; returns int, None or '.'"""
        c = ins.skip_blank_read()
        if c == tk.T_UINT:
            token = ins.read(2)
            assert len(token) == 2, 'bytecode truncated in line number pointer'
            return struct.unpack('<H', token)[0]
        elif c == b'.':
            return b'.'
        else:
            if allow_empty:
                ins.seek(-len(c), 1)
                return None
            raise error.BASICError(err)

    ###########################################################################
    # no arguments

    def _parse_nothing(self, ins):
        """Parse nothing."""
        # e.g. TRON LAH raises error but TRON will have been executed
        return
        yield # pragma: no cover

    def _parse_end(self, ins):
        """Parse end-of-statement before executing argumentless statement."""
        # e.g. SYSTEM LAH does not execute
        ins.require_end()
        # empty generator
        return
        yield # pragma: no cover

    def _skip_line(self, ins):
        """Ignore the rest of the line."""
        ins.skip_to(tk.END_LINE)
        return
        yield # pragma: no cover

    def _skip_statement(self, ins):
        """Ignore rest of statement."""
        ins.skip_to(tk.END_STATEMENT)
        return
        yield # pragma: no cover

    ###########################################################################
    # single argument

    def _parse_optional_arg(self, ins):
        """Parse statement with one optional argument."""
        yield self.parse_expression(ins, allow_empty=True)
        ins.require_end()

    def _parse_optional_arg_no_end(self, ins):
        """Parse statement with one optional argument."""
        yield self.parse_expression(ins, allow_empty=True)

    def _parse_single_arg(self, ins):
        """Parse statement with one mandatory argument."""
        yield self.parse_expression(ins)
        ins.require_end()

    def _parse_single_arg_no_end(self, ins):
        """Parse statement with one mandatory argument."""
        yield self.parse_expression(ins)

    def _parse_single_line_number(self, ins):
        """Parse statement with single line number argument."""
        yield self._parse_jumpnum(ins)

    def _parse_optional_line_number(self, ins):
        """Parse statement with optional line number argument."""
        jumpnum = None
        if ins.skip_blank() == tk.T_UINT:
            jumpnum = self._parse_jumpnum(ins)
        yield jumpnum

    ###########################################################################
    # two arguments

    def _parse_two_args(self, ins):
        """Parse POKE or OUT syntax."""
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)

    ###########################################################################
    # flow-control statements

    def _parse_run(self, ins):
        """Parse RUN syntax."""
        c = ins.skip_blank()
        if c == tk.T_UINT:
            # parse line number and ignore rest of line
            yield self._parse_jumpnum(ins)
        elif c not in tk.END_STATEMENT:
            yield None
            yield self.parse_expression(ins)
            if ins.skip_blank_read_if((b',',)):
                ins.require_read((b'R',))
                yield True
            else:
                yield False
        else:
            yield None

    def _parse_resume(self, ins):
        """Parse RESUME syntax."""
        c = ins.skip_blank()
        if c == tk.NEXT:
            yield ins.read(1)
        elif c in tk.END_STATEMENT:
            yield None
        else:
            yield self._parse_jumpnum(ins)
        ins.require_end()

    def _parse_on_error_goto(self, ins):
        """Parse ON ERROR GOTO syntax."""
        ins.require_read((tk.ERROR,))
        ins.require_read((tk.GOTO,))
        yield self._parse_jumpnum(ins)

    ###########################################################################
    # event statements

    def _parse_event_command(self, ins):
        """Parse PEN, PLAY or TIMER syntax."""
        yield ins.require_read((tk.ON, tk.OFF, tk.STOP))

    def _parse_com_command(self, ins):
        """Parse KEY, COM or STRIG syntax."""
        yield self._parse_bracket(ins)
        yield ins.require_read((tk.ON, tk.OFF, tk.STOP))

    def _parse_strig_switch(self, ins):
        """Parse STRIG ON/OFF syntax."""
        yield ins.require_read((tk.ON, tk.OFF))

    def _parse_on_event(self, ins):
        """Helper function for ON event trap definitions."""
        # token is known to be in (tk.PEN, tk.KEY, tk.TIMER, tk.PLAY, tk.COM, tk.STRIG)
        # before we call this generator
        token = ins.read_keyword_token()
        yield token
        if token != tk.PEN:
            yield self._parse_bracket(ins)
        else:
            yield None
        ins.require_read((tk.GOSUB,))
        yield self._parse_jumpnum(ins)
        ins.require_end()

    ###########################################################################
    # sound statements

    def _parse_beep(self, ins):
        """Parse BEEP syntax."""
        if self._syntax in ('pcjr', 'tandy'):
            # Tandy/PCjr BEEP ON, OFF
            yield ins.skip_blank_read_if((tk.ON, tk.OFF))
        else:
            yield None
        # if a syntax error happens, we still beeped.

    def _parse_noise(self, ins):
        """Parse NOISE syntax (Tandy/PCjr)."""
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        ins.require_end()

    def _parse_sound(self, ins):
        """Parse SOUND syntax."""
        command = None
        if self._syntax in ('pcjr', 'tandy'):
            # Tandy/PCjr SOUND ON, OFF
            command = ins.skip_blank_read_if((tk.ON, tk.OFF))
        if command:
            yield command
        else:
            yield self.parse_expression(ins)
            ins.require_read((b',',))
            dur = self.parse_expression(ins)
            yield dur
            # only look for args 3 and 4 if duration is > 0;
            # otherwise those args are a syntax error (on tandy)
            if (dur.sign() == 1) and ins.skip_blank_read_if((b',',)) and self._syntax in ('pcjr', 'tandy'):
                yield self.parse_expression(ins)
                if ins.skip_blank_read_if((b',',)):
                    yield self.parse_expression(ins)
                else:
                    yield None
            else:
                yield None
                yield None
        ins.require_end()

    def _parse_play(self, ins):
        """Parse PLAY (music) syntax."""
        if self._syntax in ('pcjr', 'tandy'):
            for _ in range(3):
                last = self.parse_expression(ins, allow_empty=True)
                yield last
                if not ins.skip_blank_read_if((b',',)):
                    break
            else:
                raise error.BASICError(error.STX)
            if last is None:
                raise error.BASICError(error.MISSING_OPERAND)
            ins.require_end()
        else:
            yield self.parse_expression(ins, allow_empty=True)
            ins.require_end(err=error.IFC)

    ###########################################################################
    # memory and machine port statements

    def _parse_def_seg(self, ins):
        """Parse DEF SEG syntax."""
        # must be uppercase in tokenised form, otherwise syntax error
        ins.require_read((tk.W_SEG,))
        if ins.skip_blank_read_if((tk.O_EQ,)):
            yield self.parse_expression(ins)
        else:
            yield None

    def _parse_def_usr(self, ins):
        """Parse DEF USR syntax."""
        ins.require_read((tk.USR,))
        yield ins.skip_blank_read_if(tk.DIGIT)
        ins.require_read((tk.O_EQ,))
        yield self.parse_expression(ins)

    def _parse_bload(self, ins):
        """Parse BLOAD syntax."""
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((b',',)):
            yield self.parse_expression(ins)
        else:
            yield None
        ins.require_end()

    def _parse_bsave(self, ins):
        """Parse BSAVE syntax."""
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        ins.require_end()

    def _parse_call(self, ins):
        """Parse CALL and CALLS syntax."""
        yield self.parse_name(ins)
        if ins.skip_blank_read_if((b'(',)):
            while True:
                yield self._parse_variable(ins)
                if not ins.skip_blank_read_if((b',',)):
                    break
            ins.require_read((b')',))
        ins.require_end()

    def _parse_wait(self, ins):
        """Parse WAIT syntax."""
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((b',',)):
            yield self.parse_expression(ins)
        else:
            yield None
        ins.require_end()

    def _parse_call_extension(self, ins):
        """Parse extension statement."""
        yield ins.read_name()
        while True:
            yield self.parse_expression(ins, allow_empty=True)
            if not ins.skip_blank_read_if((b',',)):
                break

    ###########################################################################
    # disk statements

    def _parse_name(self, ins):
        """Parse NAME syntax."""
        yield self.parse_expression(ins)
        # AS is not a tokenised word
        ins.require_read((tk.W_AS,))
        yield self.parse_expression(ins)

    ###########################################################################
    # clock statements

    def _parse_time_date(self, ins):
        """Parse TIME$ or DATE$ syntax."""
        ins.require_read((tk.O_EQ,))
        yield self.parse_expression(ins)
        ins.require_end()

    ##########################################################
    # code statements

    def _parse_delete_llist(self, ins):
        """Parse DELETE syntax."""
        yield self._parse_line_range(ins)
        ins.require_end()

    def _parse_edit(self, ins):
        """Parse EDIT syntax."""
        if ins.skip_blank() not in tk.END_STATEMENT:
            yield self._parse_jumpnum_or_dot(ins, err=error.IFC)
        else:
            yield None
        ins.require_end(err=error.IFC)

    def _parse_auto(self, ins):
        """Parse AUTO syntax."""
        yield self._parse_jumpnum_or_dot(ins, allow_empty=True)
        if ins.skip_blank_read_if((b',',)):
            inc = self._parse_optional_jumpnum(ins)
            if inc is None:
                raise error.BASICError(error.IFC)
            else:
                yield inc
        else:
            yield None
        ins.require_end()

    def _parse_save(self, ins):
        """Parse SAVE syntax."""
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((b',',)):
            yield ins.require_read((b'A', b'a', b'P', b'p'))
        else:
            yield None
        ins.require_end()

    def _parse_list(self, ins):
        """Parse LIST syntax."""
        yield self._parse_line_range(ins)
        if ins.skip_blank_read_if((b',',)):
            yield self.parse_expression(ins)
            # ignore everything after file spec
            ins.skip_to(tk.END_LINE)
        else:
            yield None
            ins.require_end()

    def _parse_load(self, ins):
        """Parse LOAD syntax."""
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((b',',)):
            yield ins.require_read((b'R', b'r'))
        else:
            yield None
        ins.require_end()

    def _parse_renum(self, ins):
        """Parse RENUM syntax."""
        new, old, step = None, None, None
        if ins.skip_blank() not in tk.END_STATEMENT:
            new = self._parse_jumpnum_or_dot(ins, allow_empty=True)
            if ins.skip_blank_read_if((b',',)):
                old = self._parse_jumpnum_or_dot(ins, allow_empty=True)
                if ins.skip_blank_read_if((b',',)):
                    # the number not optional at all if a comma is given
                    # but we need to control the error type
                    step = self._parse_optional_jumpnum(ins)
                    # negative numbers leave us before the end and raise STX
                    ins.require_end()
                    # empty afer comma raises IFC
                    if step is None:
                        raise error.BASICError(error.IFC)
        # we need require_end in both places to get correct error sequencing
        ins.require_end()
        for n in (new, old, step):
            yield n

    def _parse_chain(self, ins):
        """Parse CHAIN syntax."""
        yield ins.skip_blank_read_if((tk.MERGE,)) is not None
        yield self.parse_expression(ins)
        jumpnum, common_all, delete_range = None, False, True
        if ins.skip_blank_read_if((b',',)):
            # check for an expression that indicates a line in the other program.
            # This is not stored as a jumpnum (to avoid RENUM)
            jumpnum = self.parse_expression(ins, allow_empty=True)
            if ins.skip_blank_read_if((b',',)):
                common_all = ins.skip_blank_read_if((tk.W_ALL,), 3)
                if common_all:
                    # CHAIN "file", , ALL, DELETE
                    delete_range = ins.skip_blank_read_if((b',',))
                # CHAIN "file", , DELETE
        yield jumpnum
        yield common_all
        if delete_range and ins.skip_blank_read_if((tk.DELETE,)):
            from_line = self._parse_optional_jumpnum(ins)
            if ins.skip_blank_read_if((tk.O_MINUS,)):
                to_line = self._parse_optional_jumpnum(ins)
            else:
                to_line = from_line
            error.throw_if(not to_line)
            delete_lines = (from_line, to_line)
            # ignore rest if preceded by comma
            if ins.skip_blank_read_if((b',',)):
                ins.skip_to(tk.END_STATEMENT)
            yield delete_lines
        else:
            yield None
        ins.require_end()

    ###########################################################################
    # file statements

    def _parse_open(self, ins):
        """Parse OPEN syntax."""
        yield self.parse_expression(ins)
        first_syntax = ins.skip_blank_read_if((b',',))
        yield first_syntax
        if first_syntax:
            args = self._parse_open_first(ins)
        else:
            args = self._parse_open_second(ins)
        for a in args:
            yield a

    def _parse_open_first(self, ins):
        """Parse OPEN first ('old') syntax."""
        ins.skip_blank_read_if((b'#',))
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((b',',)):
            yield self.parse_expression(ins)
        else:
            yield None

    def _parse_open_second(self, ins):
        """Parse OPEN second ('new') syntax."""
        # mode clause
        if ins.skip_blank_read_if((tk.FOR,)):
            # read mode word
            if ins.skip_blank_read_if((tk.INPUT,)):
                yield b'I'
            else:
                mode_dict = {tk.W_OUTPUT: b'O', tk.W_RANDOM: b'R', tk.W_APPEND: b'A'}
                word = ins.skip_blank_read_if(mode_dict, 6)
                if word is not None:
                    yield mode_dict[word]
                else:
                    raise error.BASICError(error.STX)
        else:
            yield None
        # ACCESS clause
        if ins.skip_blank_read_if((tk.W_ACCESS,), 6):
            yield self._parse_read_write(ins)
        else:
            yield None
        # LOCK clause
        if ins.skip_blank_read_if((tk.LOCK,), 2):
            yield self._parse_read_write(ins)
        else:
            yield ins.skip_blank_read_if((tk.W_SHARED,), 6)
        # AS file number clause
        ins.require_read((tk.W_AS,))
        ins.skip_blank_read_if((b'#',))
        yield self.parse_expression(ins)
        # LEN clause
        if ins.skip_blank_read_if((tk.LEN,), 2):
            ins.require_read((tk.O_EQ,))
            yield self.parse_expression(ins)
        else:
            yield None

    def _parse_read_write(self, ins):
        """Parse access mode for OPEN."""
        d = ins.skip_blank_read_if((tk.READ, tk.WRITE))
        if d == tk.WRITE:
            return b'W'
        elif d == tk.READ:
            return b'RW' if ins.skip_blank_read_if((tk.WRITE,)) else b'R'
        raise error.BASICError(error.STX)

    def _parse_close(self, ins):
        """Parse CLOSE syntax."""
        if ins.skip_blank() not in tk.END_STATEMENT:
            while True:
                # if an error occurs, the files parsed before are closed anyway
                ins.skip_blank_read_if((b'#',))
                yield self.parse_expression(ins)
                if not ins.skip_blank_read_if((b',',)):
                    break

    def _parse_field(self, ins):
        """Parse FIELD syntax."""
        ins.skip_blank_read_if((b'#',))
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((b',',)):
            while True:
                yield self.parse_expression(ins)
                ins.require_read((tk.W_AS,), err=error.IFC)
                yield self._parse_variable(ins)
                if not ins.skip_blank_read_if((b',',)):
                    break

    def _parse_lock_unlock(self, ins):
        """Parse LOCK or UNLOCK syntax."""
        ins.skip_blank_read_if((b'#',))
        yield self.parse_expression(ins)
        if not ins.skip_blank_read_if((b',',)):
            ins.require_end()
            yield None
            yield None
        else:
            expr = self.parse_expression(ins, allow_empty=True)
            yield expr
            if ins.skip_blank_read_if((tk.TO,)):
                yield self.parse_expression(ins)
            elif expr is not None:
                yield None
            else:
                raise error.BASICError(error.MISSING_OPERAND)

    def _parse_ioctl(self, ins):
        """Parse IOCTL syntax."""
        ins.skip_blank_read_if((b'#',))
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)

    def _parse_put_get_file(self, ins):
        """Parse PUT and GET syntax."""
        ins.skip_blank_read_if((b'#',))
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((b',',)):
            yield self.parse_expression(ins)
        else:
            yield None

    ###########################################################################
    # graphics statements

    def _parse_pair(self, ins):
        """Parse coordinate pair."""
        ins.require_read((b'(',))
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        ins.require_read((b')',))

    def _parse_pset_preset(self, ins):
        """Parse PSET and PRESET syntax."""
        yield ins.skip_blank_read_if((tk.STEP,))
        for c in self._parse_pair(ins):
            yield c
        if ins.skip_blank_read_if((b',',)):
            yield self.parse_expression(ins)
        else:
            yield None
        ins.require_end()

    def _parse_window(self, ins):
        """Parse WINDOW syntax."""
        screen = ins.skip_blank_read_if((tk.SCREEN,))
        yield screen
        if ins.skip_blank() == b'(':
            for c in self._parse_pair(ins):
                yield c
            ins.require_read((tk.O_MINUS,))
            for c in self._parse_pair(ins):
                yield c
        elif screen:
            raise error.BASICError(error.STX)

    def _parse_circle(self, ins):
        """Parse CIRCLE syntax."""
        yield ins.skip_blank_read_if((tk.STEP,))
        for c in self._parse_pair(ins):
            yield c
        ins.require_read((b',',))
        last = self.parse_expression(ins)
        yield last
        for count_args in range(4):
            if ins.skip_blank_read_if((b',',)):
                last = self.parse_expression(ins, allow_empty=True)
                yield last
            else:
                break
        if last is None:
            raise error.BASICError(error.MISSING_OPERAND)
        for _ in range(count_args, 4):
            yield None
        ins.require_end()

    def _parse_paint(self, ins):
        """Parse PAINT syntax."""
        yield ins.skip_blank_read_if((tk.STEP,))
        for last in self._parse_pair(ins):
            yield last
        for count_args in range(3):
            if ins.skip_blank_read_if((b',',)):
                last = self.parse_expression(ins, allow_empty=True)
                yield last
            else:
                break
        if last is None:
            raise error.BASICError(error.MISSING_OPERAND)
        for _ in range(count_args, 3):
            yield None

    def _parse_view(self, ins):
        """Parse VIEW syntax."""
        yield ins.skip_blank_read_if((tk.SCREEN,))
        if ins.skip_blank() == b'(':
            for c in self._parse_pair(ins):
                yield c
            ins.require_read((tk.O_MINUS,))
            for c in self._parse_pair(ins):
                yield c
            if ins.skip_blank_read_if((b',',)):
                yield self.parse_expression(ins)
            else:
                yield None
            if ins.skip_blank_read_if((b',',)):
                yield self.parse_expression(ins)
            else:
                yield None

    def _parse_line(self, ins):
        """Parse LINE syntax."""
        if ins.skip_blank() in (b'(', tk.STEP):
            yield ins.skip_blank_read_if((tk.STEP,))
            for c in self._parse_pair(ins):
                yield c
        else:
            for _ in range(3):
                yield None
        ins.require_read((tk.O_MINUS,))
        yield ins.skip_blank_read_if((tk.STEP,))
        for c in self._parse_pair(ins):
            yield c
        if ins.skip_blank_read_if((b',',)):
            expr = self.parse_expression(ins, allow_empty=True)
            yield expr
            if ins.skip_blank_read_if((b',',)):
                if ins.skip_blank_read_if((b'B',)):
                    shape = b'BF' if ins.skip_blank_read_if((b'F',)) else b'B'
                else:
                    shape = None
                yield shape
                if ins.skip_blank_read_if((b',',)):
                    yield self.parse_expression(ins)
                else:
                    # mustn't end on a comma
                    # mode == '' if nothing after previous comma
                    error.throw_if(not shape, error.STX)
                    yield None
            elif not expr:
                raise error.BASICError(error.MISSING_OPERAND)
            else:
                yield None
                yield None
        else:
            yield None
            yield None
            yield None
        ins.require_end()

    def _parse_get_graph(self, ins):
        """Parse graphics GET syntax."""
        # don't accept STEP for first coord
        for c in self._parse_pair(ins):
            yield c
        ins.require_read((tk.O_MINUS,))
        yield ins.skip_blank_read_if((tk.STEP,))
        for c in self._parse_pair(ins):
            yield c
        ins.require_read((b',',))
        yield self.parse_name(ins)
        ins.require_end()

    def _parse_put_graph(self, ins):
        """Parse graphics PUT syntax."""
        # don't accept STEP
        for c in self._parse_pair(ins):
            yield c
        ins.require_read((b',',))
        yield self.parse_name(ins)
        if ins.skip_blank_read_if((b',',)):
            yield ins.require_read((tk.PSET, tk.PRESET, tk.AND, tk.OR, tk.XOR))
        else:
            yield None
        ins.require_end()

    ###########################################################################
    # variable statements

    def _parse_clear(self, ins):
        """Parse CLEAR syntax."""
        # integer expression allowed but ignored
        yield self.parse_expression(ins, allow_empty=True)
        if ins.skip_blank_read_if((b',',)):
            exp1 = self.parse_expression(ins, allow_empty=True)
            yield exp1
            if not ins.skip_blank_read_if((b',',)):
                if not exp1:
                    raise error.BASICError(error.STX)
            else:
                # set aside stack space for GW-BASIC. The default is the previous stack space size.
                exp2 = self.parse_expression(ins, allow_empty=True)
                yield exp2
                if self._syntax in ('pcjr', 'tandy') and ins.skip_blank_read_if((b',',)):
                    # Tandy/PCjr: select video memory size
                    yield self.parse_expression(ins)
                elif not exp2:
                    raise error.BASICError(error.STX)
        ins.require_end()

    def _parse_def_fn(self, ins):
        """DEF FN: define a function."""
        ins.require_read((tk.FN,))
        yield self.parse_name(ins)

    def _parse_var_list(self, ins):
        """Generator: lazily parse variable list."""
        while True:
            yield self._parse_variable(ins)
            if not ins.skip_blank_read_if((b',',)):
                break

    def _parse_deftype(self, ins):
        """Parse DEFSTR/DEFINT/DEFSNG/DEFDBL syntax."""
        while True:
            start = ins.require_read(tuple(iterchar(LETTERS)))
            stop = None
            if ins.skip_blank_read_if((tk.O_MINUS,)):
                stop = ins.require_read(tuple(iterchar(LETTERS)))
            yield start, stop
            if not ins.skip_blank_read_if((b',',)):
                break

    def _parse_erase(self, ins):
        """Parse ERASE syntax."""
        while True:
            yield self.parse_name(ins)
            if not ins.skip_blank_read_if((b',',)):
                break

    def _parse_let(self, ins):
        """Parse LET, LSET or RSET syntax."""
        yield self._parse_variable(ins)
        ins.require_read((tk.O_EQ,))
        # we're not using a temp string here
        # as it would delete the new string generated by let if applied to a code literal
        yield self.parse_expression(ins)

    def _parse_mid(self, ins):
        """Parse MID$ syntax."""
        # do not use require_read as we don't allow whitespace here
        if ins.read(1) != b'(':
            raise error.BASICError(error.STX)
        yield self._parse_variable(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((b',',)):
            yield self.parse_expression(ins)
        else:
            yield None
        ins.require_read((b')',))
        ins.require_read((tk.O_EQ,))
        # we're not using a temp string here
        # as it would delete the new string generated by midset if applied to a code literal
        yield self.parse_expression(ins)
        ins.require_end()

    def _parse_option_base(self, ins):
        """Parse OPTION BASE syntax."""
        ins.require_read((tk.W_BASE,))
        # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
        yield ins.require_read((b'0', b'1'))

    def _parse_prompt(self, ins):
        """Helper function for INPUT: parse prompt definition."""
        # ; to avoid echoing newline
        newline = not ins.skip_blank_read_if((b';',))
        # parse prompt
        prompt, following = b'', b';'
        if ins.skip_blank() == b'"':
            # only literal allowed, not a string expression
            prompt = ins.read_string().strip(b'"')
            following = ins.require_read((b';', b','))
        return newline, prompt, following

    def _parse_input(self, ins):
        """Parse INPUT syntax."""
        if ins.skip_blank_read_if((b'#',)):
            yield self.parse_expression(ins)
            ins.require_read((b',',))
        else:
            yield None
            yield self._parse_prompt(ins)
        for arg in self._parse_var_list(ins):
            yield arg

    def _parse_line_input(self, ins):
        """Parse LINE INPUT syntax."""
        ins.require_read((tk.INPUT,))
        if ins.skip_blank_read_if((b'#',)):
            yield self.parse_expression(ins)
            ins.require_read((b',',))
        else:
            yield None
            yield self._parse_prompt(ins)
        # get string variable
        yield self._parse_variable(ins)

    def _parse_restore(self, ins):
        """Parse RESTORE syntax."""
        if ins.skip_blank() == tk.T_UINT:
            yield self._parse_jumpnum(ins)
            ins.require_end()
        else:
            # undefined line number for syntax errors if no line number given
            ins.require_end(err=error.UNDEFINED_LINE_NUMBER)
            yield None

    def _parse_swap(self, ins):
        """Parse SWAP syntax."""
        yield self._parse_variable(ins)
        ins.require_read((b',',))
        yield self._parse_variable(ins)

    ###########################################################################
    # console / text screen statements

    def _parse_key_macro(self, ins):
        """Parse KEY ON/OFF/LIST syntax."""
        yield ins.read_keyword_token()

    def _parse_cls(self, ins):
        """Parse CLS syntax."""
        if self._syntax != 'pcjr':
            yield self.parse_expression(ins, allow_empty=True)
            # optional comma
            if not ins.skip_blank_read_if((b',',)):
                ins.require_end(err=error.IFC)
        else:
            yield None

    def _parse_color(self, ins):
        """Parse COLOR syntax."""
        last = self.parse_expression(ins, allow_empty=True)
        yield last
        if ins.skip_blank_read_if((b',',)):
            # unlike LOCATE, ending in any number of commas is a Missing Operand
            while True:
                last = self.parse_expression(ins, allow_empty=True)
                yield last
                if not ins.skip_blank_read_if((b',',)):
                    break
            if last is None:
                raise error.BASICError(error.MISSING_OPERAND)
        elif last is None:
            raise error.BASICError(error.IFC)

    def _parse_palette(self, ins):
        """Parse PALETTE syntax."""
        attrib = self.parse_expression(ins, allow_empty=True)
        yield attrib
        if attrib is None:
            yield None
            ins.require_end()
        else:
            ins.require_read((b',',))
            colour = self.parse_expression(ins, allow_empty=True)
            yield colour
            error.throw_if(attrib is None or colour is None, error.STX)

    def _parse_palette_using(self, ins):
        """Parse PALETTE USING syntax."""
        ins.require_read((tk.USING,))
        array_name, start_indices = self._parse_variable(ins)
        yield array_name, start_indices
        # brackets are not optional
        error.throw_if(not start_indices, error.STX)

    def _parse_locate(self, ins):
        """Parse LOCATE syntax."""
        #row, col, cursor, start, stop
        for i in range(5):
            yield self.parse_expression(ins, allow_empty=True)
            # note that LOCATE can end on a 5th comma but no stuff allowed after it
            if not ins.skip_blank_read_if((b',',)):
                break
        ins.require_end()

    def _parse_view_print(self, ins):
        """Parse VIEW PRINT syntax."""
        ins.require_read((tk.PRINT,))
        start = self.parse_expression(ins, allow_empty=True)
        yield start
        if start is not None:
            ins.require_read((tk.TO,))
            yield self.parse_expression(ins)
        else:
            yield None
        ins.require_end()

    def _parse_write(self, ins):
        """Parse WRITE syntax."""
        if ins.skip_blank_read_if((b'#',)):
            yield self.parse_expression(ins)
            ins.require_read((b',',))
        else:
            yield None
        if ins.skip_blank() not in tk.END_STATEMENT:
            while True:
                yield self.parse_expression(ins)
                if not ins.skip_blank_read_if((b',', b';')):
                    break
            ins.require_end()

    def _parse_width(self, ins):
        """Parse WIDTH syntax."""
        d = ins.skip_blank_read_if((b'#', tk.LPRINT))
        if d:
            if d == b'#':
                yield self.parse_expression(ins)
                ins.require_read((b',',))
            else:
                yield tk.LPRINT
            yield self.parse_expression(ins)
        else:
            yield None
            if ins.peek() in set(iterchar(DIGITS)) | set(tk.NUMBER):
                expr = self.expression_parser.read_number_literal(ins)
            else:
                expr = self.parse_expression(ins)
            yield expr
            if isinstance(expr, values.String):
                ins.require_read((b',',))
                yield self.parse_expression(ins)
            elif not ins.skip_blank_read_if((b',',)):
                yield None
                ins.require_end(error.IFC)
            else:
                # parse dummy number rows setting
                yield self.parse_expression(ins, allow_empty=True)
                # trailing comma is accepted
                ins.skip_blank_read_if((b',',))
        ins.require_end()

    def _parse_screen(self, ins):
        """Parse SCREEN syntax."""
        # erase can only be set on pcjr/tandy 5-argument syntax
        # all but last arguments are optional and may be followed by a comma
        argcount = 0
        while True:
            last = self.parse_expression(ins, allow_empty=True)
            yield last
            argcount += 1
            if not ins.skip_blank_read_if((b',',)):
                break
        if last is None:
            if self._syntax == 'tandy' and argcount == 1:
                raise error.BASICError(error.IFC)
            raise error.BASICError(error.MISSING_OPERAND)
        for _ in range(argcount, 5):
            yield None
        ins.require_end()

    def _parse_pcopy(self, ins):
        """Parse PCOPY syntax."""
        yield self.parse_expression(ins)
        ins.require_read((b',',))
        yield self.parse_expression(ins)
        ins.require_end()

    def _parse_print(self, ins, parse_file):
        """Parse PRINT or LPRINT syntax."""
        if parse_file:
            if ins.skip_blank_read_if((b'#',)):
                yield self.parse_expression(ins)
                ins.require_read((b',',))
            else:
                yield None
        while True:
            d = ins.skip_blank_read()
            if d in tk.END_STATEMENT:
                ins.seek(-len(d), 1)
                break
            elif d == tk.USING:
                yield (tk.USING, None)
                yield self.parse_expression(ins)
                ins.require_read((b';',))
                has_args = False
                while True:
                    expr = self.parse_expression(ins, allow_empty=True)
                    yield expr
                    if expr is None:
                        ins.require_end()
                        # need at least one argument after format string
                        if not has_args:
                            raise error.BASICError(error.MISSING_OPERAND)
                        break
                    has_args = True
                    if not ins.skip_blank_read_if((b';', b',')):
                        break
                break
            elif d in (b',', b';'):
                yield (d, None)
            elif d in (tk.SPC, tk.TAB):
                num = self.parse_expression(ins)
                ins.require_read((b')',))
                yield (d, num)
            else:
                ins.seek(-len(d), 1)
                yield (None, None)
                yield self.parse_expression(ins)

    ###########################################################################
    # loops and branches

    def _parse_on_jump(self, ins):
        """ON: calculated jump."""
        yield self.parse_expression(ins)
        yield ins.require_read((tk.GOTO, tk.GOSUB))
        while True:
            num = self._parse_optional_jumpnum(ins)
            yield num
            if not ins.skip_blank_read_if((b',',)):
                break
        ins.require_end()

    def _parse_if(self, ins):
        """IF: enter branching statement."""
        # avoid overflow: don't use bools.
        condition = self.parse_expression(ins)
        # optional comma
        ins.skip_blank_read_if((b',',))
        ins.require_read((tk.THEN, tk.GOTO))
        # THEN and GOTO tokens both have length 1
        start_pos = ins.tell() - 1
        # allow cofunction to evaluate condition
        branch = yield condition
        # we only even parse the ELSE clause if this is false
        if branch:
            jumpnum = self._parse_optional_jumpnum(ins)
            yield jumpnum
            if jumpnum is None:
                ins.seek(start_pos)
        else:
            # find correct ELSE block, if any
            # ELSEs may be nested in the THEN clause
            nesting_level = 0
            while True:
                d = ins.skip_to_read(tk.END_STATEMENT + (tk.IF,))
                if d == tk.IF:
                    # nesting step on IF. (it's less convenient to count THENs
                    # because they could be THEN or GOTO)
                    nesting_level += 1
                elif d == b':':
                    # :ELSE is ELSE; may be whitespace in between. no : means it's ignored.
                    if ins.skip_blank_read_if((tk.ELSE,)):
                        # ELSE has length 1
                        start_pos = ins.tell() - 1
                        if nesting_level > 0:
                            nesting_level -= 1
                        else:
                            jumpnum = self._parse_optional_jumpnum(ins)
                            yield jumpnum
                            if jumpnum is None:
                                ins.seek(start_pos)
                            break
                else:
                    # end of line, don't look for line number
                    ins.seek(-len(d), 1)
                    yield None
                    break

    def _parse_for(self, ins):
        """Parse FOR syntax."""
        # read variable
        yield self.parse_name(ins)
        ins.require_read((tk.O_EQ,))
        yield self.parse_expression(ins)
        ins.require_read((tk.TO,))
        yield self.parse_expression(ins)
        if ins.skip_blank_read_if((tk.STEP,)):
            yield self.parse_expression(ins)
        else:
            yield None
        ins.require_end()

    def _parse_next(self, ins):
        """Parse NEXT syntax."""
        # note that next_ will not run the full generator if it finds a loop to iterate
        while True:
            # optional var name, errors have been checked during _find_next scan
            if ins.skip_blank() not in tk.END_STATEMENT + (b',',):
                yield self.parse_name(ins)
            else:
                yield None
            # done if we're not jumping into a comma'ed NEXT
            if not ins.skip_blank_read_if((b',')):
                break
