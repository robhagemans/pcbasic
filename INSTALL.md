### Installing PC-BASIC from the source distribution
These instructions cover the steps needed to install the development version of PC-BASIC from the source TGZ distribution
or directly from the Git repository.

#### You probably don't need to read this file ####
General installation instructions for PC-BASIC can be found in `README.md`.
The instructions there cover the most common platforms and use cases. If the
options described there are not applicable or you prefer to install from source,
please consult the notes below.

#### Installation from the Python distribution ####
Download the Python distribution of PC-BASIC and unpack the TGZ archive.
The following packages are needed or recommended when installing PC-BASIC from the Python distribution:

| Package                                                                           | OS                 | Status       | Used for
|-----------------------------------------------------------------------------------|--------------------|--------------|----------------------------------------
| [Python 2.7.12](https://www.python.org/downloads/release/python-2712/)            | all                | required     |
| [Setuptools](https://pypi.python.org/pypi/setuptools)                             | all                | required     |
| [PyWin32](https://sourceforge.net/projects/pywin32/)                              | Windows            | required     |
| [PySDL2](https://pysdl2.readthedocs.org/en/latest/)                               | all                | recommended  | sound and graphics
| [NumPy](https://sourceforge.net/projects/numpy/files/)                            | all                | recommended  | sound and graphics
| [PySerial 3.4](https://pypi.python.org/pypi/pyserial)                             | all                | optional     | physical or emulated serial port access
| [PyParallel 0.2](https://sourceforge.net/projects/pyserial/files/pyparallel/0.2/) | Windows, Linux     | optional     | physical parallel port access
| [Pexpect](http://pexpect.readthedocs.org/en/latest/install.html)                  | OSX, Linux, other  | optional     | `SHELL` command
| [PyGame 1.9.3](http://www.pygame.org)                                             | all                | optional     | sound and graphics (PyGame interface)
| [PyAudio](http://people.csail.mit.edu/hubert/pyaudio/)                            | all                | experimental | sound (PortAudio engine)

In this list, _other_ refers to operating systems other than Windows, Linux or OSX.

On **Windows**, first install Python 2.7 from the web site linked on top. Most dependencies can then be installed with `pip`:

        pip install pypiwin32 pysdl2 numpy pygame pyaudio pyserial

If you require access to a physical parallel port, download PyParallel from the web site linked above.

The binary [ANSI|pipe](http://github.com/robhagemans/ansipipe/) executable `launcher.exe` is included with the source distribution.
Please ensure the binary is placed in the directory where `setup.py` is located. You can now run PC-BASIC with the command `launcher python -m pcbasic`. Without ANSI|pipe, PC-BASIC will run but you will
be unable to use the text-based interfaces (options `-t` and `-b`) as they will print only gibberish on the console.

On **OSX**, there are several versions of Python 2.7 and all downloads need to match your version and CPU architecture. It's a bit tricky, I'm afraid. The easiest option seems to be installing both Python and PyGame through MacPorts or Homebrew.

On **Linux distributions with APT or DNF** (including Debian, Ubuntu, Mint and Fedora), the install script will automatically install dependencies if it is run with root privileges.

The install script can also be used on **other Unix** systems or when not installing as root. The dependencies can often be installed through your package manager. For example, on Debian-based systems:

        sudo apt-get install python2.7 python-sdl2 python-numpy python-serial python-pexpect python-parallel

On Fedora:

        sudo dnf install python pysdl2 numpy pyserial python-pexpect

On FreeBSD:

        sudo pkg install python27 py27-sdl2 py27-numpy py27-serial py27-pexpect

Note that PyParallel is not available from the Fedora and FreeBSD repos. PyParallel does not support BSD; on Fedora, you'll need to install from source if you need access to physical parallel ports. However, since most modern machines do not actually have parallel ports, you probably don't need it. PyParallel is _not_ needed for printing to a CUPS or Windows printer.


#### External tools ####
On Linux, OSX and other Unix-like systems, PC-BASIC can employ the following
external command-line tools. The essential tools in this list are part of a standard system on
the platform for which they are needed; the other tools are optional.

| Tool                                      | OS                | Status      | Used for
|-------------------------------------------|-------------------|-------------|---------------------------------
| `lpr`                                     | OSX, Linux, other | essential   | printing to CUPS printers
| `paps`                                    | OSX, Linux, other | recommended | improved Unicode support for CUPS printing
| `pbcopy`  and  `pbpaste`                  | OSX               | optional    | clipboard operation with PyGame
| `beep`                                    | OSX, Linux, other | optional    | sound in cli/text interface


#### Building from GitHub source repository ####
The Python distribution of PC-BASIC described above contains precompiled documentation and Windows binaries for SDL2, SDL2_gfx and ANSI|pipe.
If you wish to use the source code as-is in the Git repo,
you'll need to build these yourself. Compiling the documentation requires the Python modules
[`lxml`](https://pypi.python.org/pypi/lxml/3.4.3) and [`markdown`](https://pypi.python.org/pypi/Markdown).
Testing additionally requires [`pylint`](https://pypi.python.org/pypi/pylint/1.7.6) and [`coverage`](https://pypi.python.org/pypi/coverage).
You'll also need [`git`](https://git-scm.com/) and all the PC-BASIC dependencies listed above.


1. Clone the repo from GitHub

        git clone --recursive https://github.com/robhagemans/pcbasic.git

2. Compile the documentation

        python setup.py build_docs

3. Run pcbasic directly from the source directory

        python -m pcbasic


To build the supporting binaries for Windows, please refer to the compilation instructions for [SDL2](https://www.libsdl.org/), [SDL2_gfx](http://www.ferzkopp.net/wordpress/2016/01/02/sdl_gfx-sdl2_gfx/) and [ANSI|pipe](http://github.com/robhagemans/ansipipe/). You will need a C compiler such as [MinGW](http://mingw.org/) or [Microsoft Visual Studio](https://www.visualstudio.com/).


#### Building `SDL2_gfx.dll` on Windows with MinGW GCC ###
This plugin is needed if
you want to use the SDL2 interface with smooth scaling. Most Linux distributions will include this with their pysdl2 package.
On Windows, you will need to compile from source. The official distribution includes a solution file for Microsoft Visual Studio;
for those who prefer to use the MinGW GCC compiler, follow these steps:  

1. Download and unpack the SDL2 binary, the SDL2 development package for MinGW and the SDL2_gfx source code archive. Note that the SDL2 development package contains several subdirectories for different architectures. You'll need the 32-bit version in `i686-w64-mingw32/`  

2. Place `SDL2.dll` in the directory where you unpacked the SDL2_gfx source code.  

3. In the MinGW shell, run  

        ./autogen.sh
        ./configure --with-sdl-prefix="/path/to/where/you/put/i686-w64-mingw32/"
        make
        gcc -shared -o SDL2_gfx.dll *.o SDL2.dll

4. Place `sdl2.dll` and `sdl2_gfx.dll` in the `pcbasic\interface` directory.  


#### Installing with PyGame ####
The preferred graphical interface is SDL2. However, a PyGame interface is also available.

The 1.9.1 release of PyGame, currently still standard on some distributions (e.g. Ubuntu 16.04 LTS),
unfortunately contains a few bugs that have been resolved in newer releases. Please use the latest
PyGame release from pygame.org, or install with `pip install pygame`.
