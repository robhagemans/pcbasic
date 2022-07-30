

### Setting up a development environment for PC-BASIC
These instructions cover the steps needed to install the development source of PC-BASIC and its dependencies. You can also follow them if you simply want to install PC-BASIC from the source repository on GitHub.

#### You won't need to read this file just to install PC-BASIC ####
General installation instructions for PC-BASIC can be found in `README.md`.
The instructions there cover the most common platforms and use cases.


#### Dependencies ####
The following packages are needed, recommended or optional when installing PC-BASIC:

| Package                                                                       | OS                 | Status       | Used for
|-------------------------------------------------------------------------------|--------------------|--------------|----------------------------------------
| [Python 3.6.9 or later](https://www.python.org/downloads/)                    | all                | required     |
| [SDL2](https://www.libsdl.org/download-2.0.php)                               | all                | recommended  | graphics and sound with `--interface=graphical`
| [PySerial 3.4](https://github.com/pyserial/pyserial)                          | all                | optional     | physical or emulated serial port access
| [PyParallel](https://github.com/pyserial/pyparallel)                          | Windows, Linux     | optional     | physical parallel port access
| [PyAudio](http://people.csail.mit.edu/hubert/pyaudio/)                        | all                | optional     | sound without SDL2

`setuptools` and `pip` are included with Python.
Once you have a working Python installation, most dependencies can be installed with `pip`:

        pip3 install pysdl2-dll pyserial

For Windows, Mac, and Linux, it is recommended to use the SDL2 and SDL2-gfx libraries provided by the [pysdl2-dll](https://github.com/a-hurst/pysdl2-dll) package.
Alternatively, you can get the library directly from [libsdl.org](https://www.libsdl.org/download-2.0.php).
Install the library in your OS's standard location for libraries. If this causes difficulties, you can alternatively place the library in `pcbasic/lib`.

[PyAudio](http://people.csail.mit.edu/hubert/pyaudio/) is only used if SDL2 is not available. The project only distributes binary wheels for Windows.
On Mac or Linux, `pip3 install pyaudio` will try to compile the module from source; for this to succeed, you need to have [the PortAudio library](http://files.portaudio.com/download.html)
and the header files for your Python version and for PortAudio installed on your system.

[PyParallel](https://github.com/pyserial/pyparallel) is only needed to access physical parallel ports, not for printing to a CUPS or Windows printer.
Note that most modern machines do not actually have parallel ports. If you have a parallel port and want to use it with PC-BASIC,
download and install PyParallel from the link above. Although a `pyparallel` package exists in on PyPI, at present this does not work
as essential libraries are missing.


#### External tools ####
PC-BASIC employs the following external command-line tools, if available:

| Tool                                      | OS                | Status      | Used for
|-------------------------------------------|-------------------|-------------|---------------------------------
| `notepad.exe`                             | Windows           | essential   | printing
| `lpr`                                     | Mac, Linux, Unix  | essential   | printing
| `paps`                                    | Mac, Linux, Unix  | recommended | improved Unicode support for printing
| `beep`                                    | Mac, Linux, Unix  | optional    | sound through PC speaker


#### Building from GitHub source repository ####
The following additional packages and tools are used for development, testing and packaging:

| Package                                                                                                        | OS                | Used for
|----------------------------------------------------------------------------------------------------------------|-------------------|-----------------
| [Git](https://git-scm.com/)                                                                                    | all               | development
| [`lxml`](https://pypi.python.org/pypi/lxml/3.4.3)                                                              | all               | documentation
| [`markdown`](https://pypi.python.org/pypi/Markdown)                                                            | all               | documentation
| [Prince](https://www.princexml.com/download/)                                                                  | all               | documentation
| [`pylint`](https://pypi.python.org/pypi/pylint/1.7.6)                                                          | all               | testing
| [`coverage`](https://pypi.python.org/pypi/coverage)                                                            | all               | testing
| [`colorama`](https://pypi.python.org/pypi/colorama)                                                            | Windows           | testing
| [`wheel`](https://pypi.python.org/pypi/wheel)                                                                  | all               | packaging
| [`twine`](https://pypi.python.org/pypi/twine)                                                                  | all               | packaging
| [`Pillow`](https://python-pillow.org/)                                                                         | all               | packaging
| [`cx_Freeze`](https://pypi.org/project/cx_Freeze/)                                                             | Windows, MacOS    | packaging
| `dpkg`                                                                                                         | Linux             | packaging
| `alien`                                                                                                        | Linux             | packaging


These are the steps to set up the local repository ready to run PC-BASIC:

1. Clone the repo from GitHub

        git clone --recursive https://github.com/robhagemans/pcbasic.git

2. Compile the documentation

        python3 -m make build_docs

3. Run pcbasic directly from the source directory

        pc-basic


#### Deprecation warnings ####

The following features are deprecated and **will be removed in the near future**:
- Python 2.7 support
- The [PyGame 1.9.3](www.pygame.org)-based interface
- The [curses](https://invisible-island.net/ncurses/)-based interface
- The option `--utf8` (use `--text-encoding=utf8`)
- The aliases `freedos`, `univga`, and `unifont` for the default font (use `--font=default`)
- Support for sound through the PC speaker
