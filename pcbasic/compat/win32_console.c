/*
Win32::Console::ANSI
Copyright (c) 2003-2014 J-L Morel. All rights reserved.
This code has been relicensed in 2015 by kind permission from J-L Morel.

win32_console module (aka ANSI|pipe aka winsi)
Copyright 2015-2018 Rob Hagemans.

Licensed under the Expat MIT licence.
See LICENSE.md or http://opensource.org/licenses/mit-license.php
*/

#define UNICODE
#define _WIN32_WINNT 0x0500
#include <Python.h>
#include <windows.h>
#include <stdio.h>
#include <process.h>
#include <string.h>
#include <wctype.h>
#include <ctype.h>
#include <io.h>

// include arch in module name
// so we can have 32bit and 64bit side by side for convenience
#ifdef _WIN64
    #define MODULE_NAME "win32_x64_console"
    #define INIT initwin32_x64_console
#else
    #define MODULE_NAME "win32_x86_console"
    #define INIT initwin32_x86_console
#endif


// define bool, for C < C99
typedef enum { false, true } bool;

// not defined in MinGW
static int wcscasecmp(wchar_t *a, wchar_t *b)
{
    while (*a && *b && towupper(*a++) == towupper(*b++));
    return (*a || *b);
}


// ============================================================================
// console globals
// ============================================================================

// handles to standard i/o streams
static HANDLE handle_cout;
static HANDLE handle_cin;
static HANDLE handle_cerr;

// termios-style flags
typedef struct {
    int echo;
    int icrnl;
    int onlcr;
} FLAGS;

// initial state
static FLAGS flags = { true, true, false };

// size of pipe buffers
#define IO_BUFLEN 1024


// ============================================================================
// colour constants
// ============================================================================

#define FOREGROUND_BLACK 0
#define FOREGROUND_WHITE FOREGROUND_RED|FOREGROUND_GREEN|FOREGROUND_BLUE

#define BACKGROUND_BLACK 0
#define BACKGROUND_WHITE BACKGROUND_RED|BACKGROUND_GREEN|BACKGROUND_BLUE

static int foregroundcolor[16] = {
      FOREGROUND_BLACK,                                       // black
      FOREGROUND_RED,                                         // red
      FOREGROUND_GREEN,                                       // green
      FOREGROUND_RED|FOREGROUND_GREEN,                        // yellow
      FOREGROUND_BLUE,                                        // blue
      FOREGROUND_BLUE|FOREGROUND_RED,                         // magenta
      FOREGROUND_BLUE|FOREGROUND_GREEN,                       // cyan
      FOREGROUND_WHITE,                                       // light grey
      FOREGROUND_BLACK|FOREGROUND_INTENSITY,                  // dark grey
      FOREGROUND_RED|FOREGROUND_INTENSITY,                    // bright red
      FOREGROUND_GREEN|FOREGROUND_INTENSITY,                  // bright green
      FOREGROUND_RED|FOREGROUND_GREEN|FOREGROUND_INTENSITY,   // bright yellow
      FOREGROUND_BLUE|FOREGROUND_INTENSITY ,                  // bright blue
      FOREGROUND_BLUE|FOREGROUND_RED|FOREGROUND_INTENSITY,    // bright magenta
      FOREGROUND_BLUE|FOREGROUND_GREEN|FOREGROUND_INTENSITY,  // bright cyan
      FOREGROUND_WHITE|FOREGROUND_INTENSITY                   // white
};

static int backgroundcolor[16] = {
      BACKGROUND_BLACK,
      BACKGROUND_RED,
      BACKGROUND_GREEN,
      BACKGROUND_RED|BACKGROUND_GREEN,
      BACKGROUND_BLUE,
      BACKGROUND_BLUE|BACKGROUND_RED,
      BACKGROUND_BLUE|BACKGROUND_GREEN,
      BACKGROUND_WHITE,
      BACKGROUND_BLACK|BACKGROUND_INTENSITY,
      BACKGROUND_RED|BACKGROUND_INTENSITY,
      BACKGROUND_GREEN|BACKGROUND_INTENSITY,
      BACKGROUND_RED|BACKGROUND_GREEN|BACKGROUND_INTENSITY,
      BACKGROUND_BLUE|BACKGROUND_INTENSITY,
      BACKGROUND_BLUE|BACKGROUND_RED|BACKGROUND_INTENSITY,
      BACKGROUND_BLUE|BACKGROUND_GREEN|BACKGROUND_INTENSITY,
      BACKGROUND_WHITE|BACKGROUND_INTENSITY
};

// Table to convert the color order of the console in the ANSI order.
//static int conversion[16] = {0, 4, 2, 6, 1, 5, 3, 7, 8, 12, 10, 14, 9, 13, 11, 15};

static int foreground_default = FOREGROUND_WHITE;
static int background_default = BACKGROUND_BLACK;


// ============================================================================
// string cat
// ============================================================================

typedef struct {
    wchar_t *buffer;
    long size;
    long count;
} WSTR;

static WSTR wstr_create_empty(wchar_t *buffer, long size) {
    WSTR newstr;
    if (size > 0)
        buffer[0] = 0;
    newstr.buffer = buffer;
    newstr.size = size;
    newstr.count = 0;
    return newstr;
}

// instr is a null-terminated string
static wchar_t* wstr_write(WSTR *wstr, wchar_t *instr, long length)
{
    // length does not include the null terminator; size does
    if (wstr->count + length + 1 > wstr->size) {
        wcsncpy(wstr->buffer, instr, wstr->size - wstr->count - 1);
        wstr->buffer[wstr->count-1] = 0;
        wstr->count = wstr->size;
        return NULL;
    }
    wcscpy(wstr->buffer + wstr->count, instr);
    wstr->count += length;
    return wstr->buffer + wstr->count;
}

static wchar_t* wstr_write_char(WSTR *wstr, wchar_t c)
{
    if (wstr->count + 2 > wstr->size) {
        wstr->count = wstr->size;
        return NULL;
    }
    wstr->buffer[wstr->count++] = c;
    wstr->buffer[wstr->count] = 0;
    return wstr->buffer + wstr->count;
}


// ============================================================================
// windows console
// ============================================================================

// current attributes
typedef struct {
    int foreground;
    int background;
    bool concealed;
    bool bold;
    bool underline;
    bool rvideo;
    // scrolling
    SMALL_RECT scroll_region;
    // saved cursor position
    COORD save_pos;
    // terminal attributes
    int col;
    int row;
    int width;
    int height;
    int attr;
    HANDLE handle;
    int end;
} TERM;

static COORD onebyone = { 1, 1 };
static COORD origin = { 0, 0 };

static void console_put_char(TERM *term, wchar_t s)
{
    if (term->col >= term->width-1 && s != L'\n') {
        // do not advance cursor if we're on the last position of the
        // screen buffer, to avoid unwanted scrolling.
        SMALL_RECT dest = { term->col, term->row, term->col, term->row };
        CHAR_INFO ch;
        ch.Char.UnicodeChar = s;
        ch.Attributes = term->attr;
        WriteConsoleOutput(term->handle, &ch, onebyone, origin, &dest);
    }
    else {
        unsigned long written;
        WriteConsole(term->handle, &s, 1, &written, NULL);
    }
}

static void console_fill(TERM *term, int x, int y, int len)
{
    unsigned long written;
    COORD pos;
    pos.X = x;
    pos.Y = y;
    FillConsoleOutputCharacter(term->handle, ' ', len, pos, &written);
    FillConsoleOutputAttribute(term->handle, term->attr, len, pos, &written);
}

static void console_scroll(TERM *term, int left, int top, int right, int bot, int x, int y)
{
    SMALL_RECT rect;
    CHAR_INFO char_info;
    COORD pos;
    rect.Left = left;
    rect.Top = top;
    rect.Right = right;
    rect.Bottom = bot;
    char_info.Char.AsciiChar = ' ';
    char_info.Attributes = term->attr;
    pos.X = x;
    pos.Y = y;
    if (term->scroll_region.Bottom == term->height-2 && bot >= term->height-2 && y < top) {
        // workaround: in this particular case, Windows doesn't seem to respect the clip area.
        // first scroll everything up
        SMALL_RECT temp_scr = term->scroll_region;
        temp_scr.Bottom = term->height-1;
        rect.Bottom = term->height-1;
        ScrollConsoleScreenBuffer(term->handle, &rect, &temp_scr, pos, &char_info);
        // and then scroll the bottom back down
        pos.Y = term->height-1;
        rect.Top = term->height-1 - (top-y);
        rect.Bottom = rect.Top;
        ScrollConsoleScreenBuffer(term->handle, &rect, &temp_scr, pos, &char_info);
    }
    else
        ScrollConsoleScreenBuffer(term->handle, &rect, &(term->scroll_region), pos, &char_info);
}

static void console_set_pos(TERM *term, int x, int y)
{
    COORD pos;
    if (y < 0) y = 0;
    else if (y >= term->height) y = term->height - 1;
    if (x < 0) x = 0;
    else if (x >= term->width) x = term->width - 1;
    pos.X = x;
    pos.Y = y;
    SetConsoleCursorPosition(term->handle, pos);
}

static void console_resize(HANDLE term_handle, int width, int height)
{
    CONSOLE_SCREEN_BUFFER_INFO buf_info;
    COORD new_size;
    SMALL_RECT new_screen;
    new_size.X = width;
    GetConsoleScreenBufferInfo(handle_cout, &buf_info);
    // SetConsoleScreenBufferSize can't make the buffer smaller than the window (in either direction)
    // while SetConsoleWindowInfo can't make the window larger than the buffer (in either direction)
    // to allow for both shrinking and growing, we need to call one of the functions twice, and resize
    // each direction separately.
    // first adjust only the width
    new_size.Y = buf_info.dwSize.Y;
    new_screen.Top = 0;
    new_screen.Left = 0;
    new_screen.Bottom = buf_info.dwSize.Y - 1;
    new_screen.Right = width - 1;
    SetConsoleScreenBufferSize(term_handle, new_size);
    SetConsoleWindowInfo(term_handle, true, &new_screen);
    SetConsoleScreenBufferSize(term_handle, new_size);
    // then adjust the height
    new_size.X = width;
    new_size.Y = height;
    new_screen.Top = 0;
    new_screen.Left = 0;
    new_screen.Bottom = height - 1;
    new_screen.Right = width - 1;
    SetConsoleScreenBufferSize(term_handle, new_size);
    SetConsoleWindowInfo(term_handle, true, &new_screen);
    SetConsoleScreenBufferSize(term_handle, new_size);
}


// ============================================================================
// ANSI sequences
// ============================================================================

#define MAX_STRARG 1024         // max string arg length
#define MAX_ARG 16              // max number of args in an escape sequence

// current escape sequence state:
// for instance, with \e[33;45;1m we have
// prefix = '[',
// es.argc = 3, es.argv[0] = 33, es.argv[1] = 45, es.argv[2] = 1
// suffix = 'm'
typedef struct {
    wchar_t prefix;                    // escape sequence prefix ( '[' or '(' );
    wchar_t prefix2;                   // secondary prefix ( '?' );
    wchar_t suffix;                    // escape sequence suffix
    int argc;                          // escape sequence args count
    int argv[MAX_ARG];                 // escape sequence args
    wchar_t args[MAX_STRARG];          // escape sequence string arg; length in argv[1]
} SEQUENCE;

// interpret the last escape sequence scanned by ansi_print()
static void ansi_output(TERM *term, SEQUENCE es)
{
    if (es.prefix == L'[') {
        int i;
        int new_attr;
        if (es.prefix2 == L'?' && (es.suffix == L'h' || es.suffix == L'l')) {
            if (es.argc == 1 && es.argv[0] == 25) {
                CONSOLE_CURSOR_INFO curs_info;
                GetConsoleCursorInfo(term->handle, &curs_info);
                curs_info.bVisible = (es.suffix == L'h');
                SetConsoleCursorInfo(term->handle, &curs_info);
                return;
            }
        }
        // Ignore any other \e[? sequences.
        if (es.prefix2 != 0) return;
        switch (es.suffix) {
        case L'm':
            if (es.argc == 0) es.argv[es.argc++] = 0;
            for(i = 0; i < es.argc; i++) {
                switch (es.argv[i]) {
                case 0:
                    term->foreground = foreground_default;
                    term->background = background_default;
                    term->bold = false;
                    term->underline = false;
                    term->rvideo = false;
                    term->concealed = false;
                    break;
                case 1:
                    term->bold = true;
                    break;
                case 21:
                    term->bold = false;
                    break;
                case 4:
                    term->underline = true;
                    break;
                case 24:
                    term->underline = false;
                    break;
                case 7:
                    term->rvideo = true;
                    break;
                case 27:
                    term->rvideo = false;
                    break;
                case 8:
                    term->concealed = true;
                    break;
                case 28:
                    term->concealed = false;
                    break;
                }
                if ((100 <= es.argv[i]) && (es.argv[i] <= 107))
                    term->background = es.argv[i] - 100 + 8;
                else if ((90 <= es.argv[i]) && (es.argv[i] <= 97))
                    term->foreground = es.argv[i] - 90 + 8;
                else if ((40 <= es.argv[i]) && (es.argv[i] <= 47))
                    term->background = es.argv[i] - 40;
                else if ((30 <= es.argv[i]) && (es.argv[i] <= 37))
                    term->foreground = es.argv[i] - 30;
            }
            if (term->rvideo)
                new_attr = foregroundcolor[term->background] | backgroundcolor[term->foreground];
            else
                new_attr = foregroundcolor[term->foreground] | backgroundcolor[term->background];
            if (term->bold)
                new_attr |= FOREGROUND_INTENSITY;
            if (term->underline)
                new_attr |= BACKGROUND_INTENSITY;
            SetConsoleTextAttribute(term->handle, new_attr);
            return;
        case L'J':
            if (es.argc == 0) es.argv[es.argc++] = 0;   // ESC[J == ESC[0J
            if (es.argc != 1) return;
            switch (es.argv[0]) {
            case 0:
                // ESC[0J erase from cursor to end of display
                console_fill(term, term->col, term->row,
                        (term->height-term->row-1)*term->width + term->width-term->col-1);
                return;
            case 1:
                // ESC[1J erase from start to cursor.
                console_fill(term, 0, 0, term->row*term->width + term->col + 1);
                return;
            case 2:
                // ESC[2J Clear screen and home cursor
                console_fill(term, 0, 0, term->width * term->height);
                console_set_pos(term, 0, 0);
                return;
            default :
                return;
            }
        case L'K':
            if (es.argc == 0) es.argv[es.argc++] = 0;   // ESC[K == ESC[0K
            if (es.argc != 1) return;
            switch (es.argv[0]) {
            case 0:
                // ESC[0K Clear to end of line
                console_fill(term, term->col, term->row, term->end - term->col + 1);
                return;
            case 1:
                // ESC[1K Clear from start of line to cursor
                console_fill(term, 0, term->row, term->col + 1);
                return;
            case 2:
                // ESC[2K Clear whole line.
                console_fill(term, 0, term->row, term->width);
                return;
            default :
                return;
            }
        case L'L':
            // ESC[#L Insert # blank lines.
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[L == ESC[1L
            if (es.argc != 1) return;
            console_scroll(term, 0, term->row, term->width-1, term->height-1,
                                 0, term->row+es.argv[0]);
            console_fill(term, 0, term->row, term->width*es.argv[0]);
            return;
        case L'M':
            // ESC[#M Delete # line.
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[M == ESC[1M
            if (es.argc != 1) return;
            if (es.argv[0] > term->height - term->row)
                es.argv[0] = term->height - term->row;
            console_scroll(term,
                            0, term->row+es.argv[0], term->width-1, term->height-1,
                            0, term->row);
            console_fill(term, 0, term->height-es.argv[0], term->width*es.argv[0]);
            return;
        case L'P':
            // ESC[#P Delete # characters.
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[P == ESC[1P
            if (es.argc != 1) return;
            if (term->col + es.argv[0] > term->width - 1)
                es.argv[0] = term->width - term->col;
            console_scroll(term,
                    term->col+es.argv[0], term->row, term->width-1, term->row,
                    term->col, term->row);
            console_fill(term, term->width-es.argv[0], term->row, es.argv[0]);
            return;
        case L'@':
            // ESC[#@ Insert # blank characters.
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[@ == ESC[1@
            if (es.argc != 1) return;
            if (term->col + es.argv[0] > term->width - 1)
                es.argv[0] = term->width - term->col;
            console_scroll(term,
                    term->col, term->row, term->width-1-es.argv[0], term->row,
                    term->col+es.argv[0], term->row);
            console_fill(term, term->col, term->row, es.argv[0]);
            return;
        case L'A':
            // ESC[#A Moves cursor up # lines
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[A == ESC[1A
            if (es.argc != 1) return;
            console_set_pos(term, term->col, term->row - es.argv[0]);
            return;
        case L'B':
            // ESC[#B Moves cursor down # lines
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[B == ESC[1B
            if (es.argc != 1) return;
            console_set_pos(term, term->col, term->row + es.argv[0]);
            return;
        case L'C':
            // ESC[#C Moves cursor forward # spaces
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[C == ESC[1C
            if (es.argc != 1) return;
            console_set_pos(term, term->col + es.argv[0], term->row);
            return;
        case L'D':
            // ESC[#D Moves cursor back # spaces
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[D == ESC[1D
            if (es.argc != 1) return;
            console_set_pos(term, term->col - es.argv[0], term->row);
            return;
        case L'E':
            // ESC[#E Moves cursor down # lines, column 1.
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[E == ESC[1E
            if (es.argc != 1) return;
            console_set_pos(term, 0, term->row + es.argv[0]);
            return;
        case L'F':
            // ESC[#F Moves cursor up # lines, column 1.
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[F == ESC[1F
            if (es.argc != 1) return;
            console_set_pos(term, 0, term->row - es.argv[0]);
            return;
        case L'G':
            // ESC[#G Moves cursor column # in current row.
            if (es.argc == 0) es.argv[es.argc++] = 1;   // ESC[G == ESC[1G
            if (es.argc != 1) return;
            console_set_pos(term, es.argv[0] - 1, term->row);
            return;
        case L'f':
        case L'H':
            // ESC[#;#H or ESC[#;#f Moves cursor to line #, column #
            if (es.argc == 0) {
                es.argv[es.argc++] = 1;   // ESC[G == ESC[1;1G
                es.argv[es.argc++] = 1;
            }
            if (es.argc == 1) {
                es.argv[es.argc++] = 1;   // ESC[nG == ESC[n;1G
            }
            if (es.argc > 2) return;
            console_set_pos(term, es.argv[1]-1, es.argv[0]-1);
            return;
        case L's':
            // ESC[s Saves cursor position for recall later
            if (es.argc != 0) return;
            term->save_pos.X = term->col;
            term->save_pos.Y = term->row;
            return;
        case L'u':
            // ESC[u Return to saved cursor position
            if (es.argc != 0) return;
            SetConsoleCursorPosition(term->handle, term->save_pos);
            return;
        case L'r':
            // ESC[r set scroll region
            if (es.argc == 0) {
                // ESC[r == ESC[top;botr
                term->scroll_region.Top    = 0;
                term->scroll_region.Bottom = term->height - 1;
            }
            else if (es.argc == 2) {
                term->scroll_region.Top    = es.argv[0] - 1;
                term->scroll_region.Bottom = es.argv[1] - 1;
            }
            return;
        case L'S':
            // ESC[#S scroll up # lines
            if (es.argc != 1) return;
            console_scroll(term, 0, es.argv[0], term->width-1, term->height-1, 0, 0);
            console_fill(term, 0, term->scroll_region.Bottom, term->width*es.argv[0]);
            return;
        case L'T':
            // ESC[#T scroll down # lines
            if (es.argc != 1) return;
            console_scroll(term, 0, 0, term->width-1, term->height-es.argv[0]-1, 0, es.argv[0]);
            console_fill(term, 0, term->scroll_region.Top, term->width*es.argv[0]);
            return;
        case L't':
            //ESC[8;#;#;t resize terminal to # rows, # cols
            if (es.argc < 3) return;
            if (es.argv[0] != 8) return;
            console_resize(term->handle, es.argv[2], es.argv[1]);
            return;
        }
    }
    else if (es.prefix == L']' && es.suffix == L'\x07') {
        if (es.argc != 2) return;
        switch (es.argv[0]) {
            case 2:
                // ESC]2;%sBEL: set title
                SetConsoleTitle(es.args);
                break;
            case 255:
                // ANSIpipe-only: ESC]255;%sBEL: set terminal property
                // properties supported: ECHO, ICRNL, ONLCR
                // not thread-safe, so a bit unpredictable
                // if you're using stdout and stderr at the same time.
                // special property: SUPPSTERR - suppress stderr
                if (!wcscasecmp(es.args, L"ECHO"))
                    flags.echo = true;
                else if (!wcscasecmp(es.args, L"ICRNL"))
                    flags.icrnl = true;
                else if (!wcscasecmp(es.args, L"ONLCR"))
                    flags.onlcr = true;
                break;
            case 254:
                // ANSIpipe-only: ESC]254;%sBEL: unset terminal property
                if (!wcscasecmp(es.args, L"ECHO"))
                    flags.echo = false;
                else if (!wcscasecmp(es.args, L"ICRNL"))
                    flags.icrnl = false;
                else if (!wcscasecmp(es.args, L"ONLCR"))
                    flags.onlcr = false;
                break;
        }
    }
}

// put char on string and echo
// helper function for ansi_input
void emit_char(WSTR *pwstr, wchar_t c) {
    wstr_write_char(pwstr, c);
    if (flags.echo) {
        if (c == L'\r')
            printf("\n");
        else
            printf("%lc", c);
    }
};

// retrieve utf-8 and ansi sequences from standard input. 0 == success
// length of buffer must be IO_BUFLEN
static int ansi_input(wchar_t *wide_buffer, unsigned long *count)
{
    // event buffer size:
    // -  for utf8, buflen/4 is OK as one wchar is at most 4 chars of utf8
    // -  escape codes are at most 5 ascii-128 wchars; translate into 5 chars
    // so buflen/5 events should fit in buflen wchars and buflen utf8 chars.
    // plus one char for NUL.
    WSTR wstr = wstr_create_empty(wide_buffer, IO_BUFLEN);
    INPUT_RECORD events[(IO_BUFLEN-1)/5];
    unsigned long ecount;
    unsigned int i;
    wchar_t c;
    // avoid blocking
    if (!GetNumberOfConsoleInputEvents(handle_cin, &ecount))
        return 1;
    if (!ecount) {
        *count = 0;
        return 0;
    }
    if (!ReadConsoleInput(handle_cin, events, (IO_BUFLEN-1)/5, &ecount))
        return 1;
    for (i = 0; i < ecount; ++i) {
        if (events[i].EventType == KEY_EVENT) {
            if (!events[i].Event.KeyEvent.bKeyDown) {
                if (events[i].Event.KeyEvent.wVirtualKeyCode == VK_MENU) {
                    // key-up event for unicode Alt+HEX input
                    c = events[i].Event.KeyEvent.uChar.UnicodeChar;
                    emit_char(&wstr, c);
                }
            }
            else {
                if (events[i].Event.KeyEvent.dwControlKeyState & 0xf) {
                    // ctrl or alt are down; don't parse arrow keys etc.
                    // but if any unicode is produced, send it on
                    c = events[i].Event.KeyEvent.uChar.UnicodeChar;
                    emit_char(&wstr, c);
                }
                else {
                    // insert ansi escape codes for arrow keys etc.
                    switch (events[i].Event.KeyEvent.wVirtualKeyCode) {
                    case VK_PRIOR:
                        wstr_write(&wstr, L"\x1b[5~", 4);
                        break;
                    case VK_NEXT:
                        wstr_write(&wstr, L"\x1b[6~", 4);
                        break;
                    case VK_END:
                        wstr_write(&wstr, L"\x1bOF", 3);
                        break;
                    case VK_HOME:
                        wstr_write(&wstr, L"\x1bOH", 3);
                        break;
                    case VK_LEFT:
                        wstr_write(&wstr, L"\x1b[D", 3);
                        break;
                    case VK_UP:
                        wstr_write(&wstr, L"\x1b[A", 3);
                        break;
                    case VK_RIGHT:
                        wstr_write(&wstr, L"\x1b[C", 3);
                        break;
                    case VK_DOWN:
                        wstr_write(&wstr, L"\x1b[B", 3);
                        break;
                    case VK_INSERT:
                        wstr_write(&wstr, L"\x1b[2~", 4);
                        break;
                    case VK_DELETE:
                        wstr_write(&wstr, L"\x1b[3~", 4);
                        break;
                    case VK_F1:
                        wstr_write(&wstr, L"\x1bOP", 3);
                        break;
                    case VK_F2:
                        wstr_write(&wstr, L"\x1bOQ", 3);
                        break;
                    case VK_F3:
                        wstr_write(&wstr, L"\x1bOR", 3);
                        break;
                    case VK_F4:
                        wstr_write(&wstr, L"\x1bOS", 3);
                        break;
                    case VK_F5:
                        wstr_write(&wstr, L"\x1b[15~", 5);
                        break;
                    case VK_F6:
                        wstr_write(&wstr, L"\x1b[17~", 5);
                        break;
                    case VK_F7:
                        wstr_write(&wstr, L"\x1b[18~", 5);
                        break;
                    case VK_F8:
                        wstr_write(&wstr, L"\x1b[19~", 5);
                        break;
                    case VK_F9:
                        wstr_write(&wstr, L"\x1b[20~", 5);
                        break;
                    case VK_F10:
                        wstr_write(&wstr, L"\x1b[21~", 5);
                        break;
                    case VK_F11:
                        wstr_write(&wstr, L"\x1b[23~", 5);
                        break;
                    case VK_F12:
                        wstr_write(&wstr, L"\x1b[24~", 5);
                        break;
                    default:
                        c = events[i].Event.KeyEvent.uChar.UnicodeChar;
                        emit_char(&wstr, c);
                    }
                }
                // overflow check
                if (wstr_write(&wstr, L"", 0) == NULL) {
                    fprintf(stderr, "ERROR: (ansipipe) Input buffer overflow.\n");
                    return 1;
                }
                if (flags.icrnl) {
                    // replace last char CR -> LF
                    if (wstr.buffer[wstr.count-1] == L'\r')
                        wstr.buffer[wstr.count-1] = L'\n';
                }
            }
        }
    }
    // exclude NUL terminator in reported num chars
    *count = wstr.count;
    return 0;
}


// ============================================================================
// Parser
// ============================================================================

typedef struct {
    SEQUENCE es;
    TERM term;
    int state;
} PARSER;

// initialise a new ansi sequence parser
static void parser_init(PARSER *p, HANDLE handle)
{
    CONSOLE_SCREEN_BUFFER_INFO info;
    p->state = 1;
    p->term.handle = handle;
    p->term.foreground = foreground_default;
    p->term.background = background_default;
    // initialise scroll region to full screen
    GetConsoleScreenBufferInfo(handle, &info);
    p->term.scroll_region.Left   = 0;
    p->term.scroll_region.Right  = info.dwSize.X - 1;
    p->term.scroll_region.Top    = 0;
    p->term.scroll_region.Bottom = info.dwSize.Y - 1;
    // initialise escape sequence
    p->es.prefix = 0;
    p->es.prefix2 = 0;
    p->es.suffix = 0;
    p->es.argc = 0;
    p->es.args[0] = 0;
}

// Parse the string buffer, interpret the escape sequences and print the
// characters on the console.
// If the number of arguments es.argc > MAX_ARG, only the MAX_ARG-1 firsts and
// the last arguments are processed (no es.argv[] overflow).
static void parser_print(PARSER *p, wchar_t *s, int buflen)
{
    for (; buflen && *s; --buflen, ++s) {
        // retrieve current positions and sizes
        CONSOLE_SCREEN_BUFFER_INFO info;
        GetConsoleScreenBufferInfo(p->term.handle, &info);
        p->term.col = info.dwCursorPosition.X;
        p->term.row = info.dwCursorPosition.Y;
        p->term.width = info.dwSize.X;
        p->term.height = info.dwSize.Y;
        p->term.attr = info.wAttributes;
        p->term.end = info.srWindow.Right;
        switch (p->state) {
        case 1:
            if (*s == L'\x1b') {
                p->state = 2;
            }
            else {
                if (*s) console_put_char(&p->term, p->term.concealed ? L' ' : *s);
                if (flags.onlcr && *s == L'\r') console_put_char(&p->term, L'\n');
            }
            break;
        case 2:
            if (*s == L'\x1b');       // \e\e...\e == \e
            else if (*s == L'[') {
                p->es.prefix = *s;
                p->es.prefix2 = 0;
                p->state = 3;
            }
            else if (*s == L']') {
                p->es.prefix = *s;
                p->es.prefix2 = 0;
                p->es.argc = 0;
                p->es.argv[0] = 0;
                p->state = 5;
            }
            else p->state = 1;
            break;
        case 3:
            if (iswdigit(*s)) {
                p->es.argc = 0;
                p->es.argv[0] = *s - L'0';
                p->state = 4;
            }
            else if (*s == L';') {
                p->es.argc = 1;
                p->es.argv[0] = 0;
                p->es.argv[p->es.argc] = 0;
                p->state = 4;
            }
            else if (*s == L'?') {
                p->es.prefix2 = *s;
            }
            else {
                p->es.argc = 0;
                p->es.suffix = *s;
                ansi_output(&(p->term), p->es);
                p->state = 1;
            }
            break;
        case 4:
            if (iswdigit(*s)) {
                p->es.argv[p->es.argc] = 10*p->es.argv[p->es.argc]+(*s-L'0');
            }
            else if (*s == L';') {
                if (p->es.argc < MAX_ARG-1) p->es.argc++;
                    p->es.argv[p->es.argc] = 0;
            }
            else {
                if (p->es.argc < MAX_ARG-1) p->es.argc++;
                p->es.suffix = *s;
                ansi_output(&(p->term), p->es);
                p->state = 1;
            }
            break;
        case 5:
            // ESC]%d;%sBEL
            if (iswdigit(*s)) {
                p->es.argc = 1;
                p->es.argv[0] = 10*p->es.argv[0]+(*s-L'0');
            }
            else if (*s == L';') {
                p->es.argc = 2;
                p->es.argv[1] = 0;
                p->state = 6;
            }
            else {
                p->es.suffix = *s;
                ansi_output(&(p->term), p->es);
                p->state = 1;
            }
            break;
        case 6:
            // read string argument
            if (*s != L'\x07' && p->es.argv[1] < MAX_STRARG-1) {
                p->es.args[p->es.argv[1]++] = *s;
            }
            else {
                p->es.args[p->es.argv[1]] = 0;
                p->es.suffix = *s;
                ansi_output(&(p->term), p->es);
                p->state = 1;
            }
        }
    }
}


// ============================================================================
// DLL
// ============================================================================


static PARSER global_parser = { 0 };
static int global_is_console = 0;
static unsigned long global_save_mode;
static CONSOLE_SCREEN_BUFFER_INFO global_save_console;
// read buffer
static wchar_t global_buffer[2*IO_BUFLEN];
static unsigned int available = 0;
static unsigned int offset = 0;


static void winsi_init()
{
    unsigned long dummy_mode;
    /* initialise globals */
    // stdio handles
    handle_cout = GetStdHandle(STD_OUTPUT_HANDLE);
    handle_cin = GetStdHandle(STD_INPUT_HANDLE);
    handle_cerr = GetStdHandle(STD_ERROR_HANDLE);

    /* save initial console state */
    GetConsoleScreenBufferInfo(handle_cout, &global_save_console);
    GetConsoleMode(handle_cin, &global_save_mode);

    // see http://stackoverflow.com/questions/1169591/check-if-output-is-redirected
    global_is_console = GetConsoleMode(handle_cout, &dummy_mode);
    // prepare parser
    parser_init(&global_parser, handle_cout);
}

static void winsi_close(void)
{
    /* restore console state */
    SetConsoleMode(handle_cin, global_save_mode);
    SetConsoleTextAttribute(handle_cout, global_save_console.wAttributes);
    SetConsoleScreenBufferSize(handle_cout, global_save_console.dwSize);
}


static PyObject *winsi_read(PyObject *self, PyObject * args)
{
    unsigned long received = 0;
    if (!PyArg_ParseTuple(args, ""))
		return NULL;
    Py_BEGIN_ALLOW_THREADS;
    if (!available) {
        // empty buffer, use opportunity to reset buffer
        offset = 0;
    }
    if (global_is_console) {
        // this uses IO_BUFLEN from count onwards -> need 2*IO_BUFLEN buffer
        if (ansi_input(global_buffer+offset+available, &received) != 0) {
            // fail
        }
    }
    else {
        // read directly from redirected stdin
        if (fgetws(global_buffer+offset+available, IO_BUFLEN, stdin))
            // fgets returns null-terminated string
            received = (unsigned long) wcslen(global_buffer+offset+available);
    }
    available += received;
    Py_END_ALLOW_THREADS;
    if (available >= 1) {
        --available;
        ++offset;
        return Py_BuildValue("u#", global_buffer+offset-1, 1);
    }
    return Py_BuildValue("u#", global_buffer, 0);
}

static PyObject *winsi_write(PyObject *self, PyObject * args)
{
    wchar_t *buffer;
    int count;
    if (!PyArg_ParseTuple(args, "u#", &buffer, &count))
		return NULL;
    Py_BEGIN_ALLOW_THREADS;
    if (global_is_console) parser_print(&global_parser, buffer, count);
    else printf("%S", buffer);
    Py_END_ALLOW_THREADS;
    Py_RETURN_NONE;
}


static PyObject *winsi_setraw(PyObject *self, PyObject * args)
{
    if (!PyArg_ParseTuple(args, ""))
		return NULL;
    flags.echo = false;
    flags.icrnl = false;
    flags.onlcr = false;
    Py_RETURN_NONE;
}

// restore initial state
static PyObject *winsi_unsetraw(PyObject *self, PyObject * args)
{
    if (!PyArg_ParseTuple(args, ""))
		return NULL;
    flags.echo = true;
    flags.icrnl = true;
    flags.onlcr = false;
    Py_RETURN_NONE;
}


PyMODINIT_FUNC INIT(void)
{
	PyObject *m;
	static PyMethodDef WinsiMethods[] = {
		{"read_char", winsi_read, METH_VARARGS, "Read a sequence from the console as bytes"},
        {"write", winsi_write, METH_VARARGS, "Write bytes to the console the console"},
        {"set_raw", winsi_setraw, METH_VARARGS, "Set raw console"},
        {"unset_raw", winsi_unsetraw, METH_VARARGS, "Restore cooked console"},
		{NULL, NULL, 0, NULL}
	};

    m = Py_InitModule(MODULE_NAME, WinsiMethods);
	if (!m) return;

    winsi_init();

    // stream encoding
    if (global_is_console) {
        // if we're active, we take utf-8
        if (0 != PyModule_AddStringConstant(m, "encoding", "utf-8")) return;
    } else {
        // no encoding set on non-tty streams
        // check: do we ned a new reference?
        Py_INCREF(Py_None);
        if (0 != PyModule_AddObject(m, "encoding", Py_None)) return;
    }
    // stream is a terminal
    if (0 != PyModule_AddIntConstant(m, "is_tty", global_is_console))
        return;

    Py_AtExit(*winsi_close);
}

int main(int argc, char *argv[])
{
	Py_SetProgramName(argv[0]);
	Py_Initialize();
	INIT();
}
