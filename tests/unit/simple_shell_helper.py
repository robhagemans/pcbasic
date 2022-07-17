import sys
import io

ECHO = '-e' in sys.argv[1:]
PROMPT = '-p' in sys.argv[1:]
GREET = '-g' in sys.argv[1:]
UTF16 = '-u' in sys.argv[1:]

if '/C' in sys.argv:
    idx = sys.argv.index('/C')
    command = sys.argv[idx+1]
else:
    command = ''


for term in sys.argv[1:]:
    if not term.startswith('-') and not term.startswith('/'):
        # input encoding
        encoding = term
        break
else:
    encoding = 'latin-1'


# -g -p        wine cmd.exe: CRLF, no echo, utf-8 (shell encoding), extra CRLF before prompt (seen as blank line in cmd window so keep)
# -g -p -e     windows cmd.exe: CRLF, echo including CRLF, shell encoding. extra CRLF before prompt (seen as blank line in cmd window so keep)
# -g -p -e -u  windows cmd.exe /u: same, but responses in utf-16le while input in shell encoding

if UTF16:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-16le', newline='')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-16le', newline='')
else:
    # set universal newlines
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=sys.stdout.encoding, newline='')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding=sys.stderr.encoding, newline='')

def run_command(inp):
    if inp.startswith('echo '):
        sys.stdout.write(f'{inp[5:]}\r\n')
        sys.stdout.flush()
    else:
        sys.stderr.write(f"'{inp}' is not recognised.\r\n")
        sys.stderr.flush()


if command:
    run_command(command)

else:
    if GREET:
        sys.stdout.write('Testing Shell')
        sys.stdout.flush()

    while True:
        if PROMPT:
            sys.stdout.write('\r\n> ')
            sys.stdout.flush()
        inp = b''
        while True:
            c = sys.stdin.buffer.read(1)
            if c == b'\n':
                break
            elif c != b'\r':
                inp += c
        sys.stdout.flush()
        inp = inp.decode(encoding)
        if ECHO:
            sys.stdout.write(inp + '\r\n')
            sys.stdout.flush()
        if inp == 'exit':
            break
        else:
            run_command(inp)
