### Installing PC-BASIC from the source distribution
These instructions cover the steps needed to install the development version of PC-BASIC from source.

#### You probably don't need to read this file ####
General installation instructions for PC-BASIC can be found in `README.md`.
The instructions there cover the most common platforms and use cases. If the
options described there are not applicable or you prefer to install from source,
please consult the notes below.

#### Required packages ####
The following packages are needed or recommended when installing PC-BASIC from the Python distribution:

| Package                                                                           | OS                 | Status       | Used for
|-----------------------------------------------------------------------------------|--------------------|--------------|----------------------------------------
| [Python 2.7.12](https://www.python.org/downloads/release/python-2712/)            | all                | required     |
| [Setuptools](https://pypi.python.org/pypi/setuptools)                             | all                | required     |
| [PySDL2](https://pysdl2.readthedocs.org/en/latest/)                               | all                | recommended  | sound and graphics
| [NumPy](https://sourceforge.net/projects/numpy/files/)                            | all                | recommended  | sound and graphics
| [PySerial 3.4](https://pypi.python.org/pypi/pyserial)                             | all                | optional     | physical or emulated serial port access
| [PyParallel 0.2](https://sourceforge.net/projects/pyserial/files/pyparallel/0.2/) | Windows, Linux     | optional     | physical parallel port access
| [Pexpect](http://pexpect.readthedocs.org/en/latest/install.html)                  | Mac, Linux, Unix   | optional     | `SHELL` command
| [PyGame 1.9.3](http://www.pygame.org)                                             | all                | optional     | sound and graphics (PyGame interface)
| [PyAudio](http://people.csail.mit.edu/hubert/pyaudio/)                            | all                | experimental | sound (PortAudio engine)


Once you have a working Python installation, most dependencies can be installed with `pip`:

        pip install pypiwin32 pysdl2 numpy pygame pyaudio pyserial pexpect

`setuptools` and `pip` are included with Python. If you require access to a physical parallel port,
download PyParallel from the web site linked above. This is only supported on Windows and Linux.
However, since most modern machines do not actually have parallel ports, you probably don't need it.
PyParallel is _not_ needed for printing to a CUPS or Windows printer.

To use the graphical interface, you will also need to install the [`SDL2`](https://www.libsdl.org/download-2.0.php) library, which is _not_ included in the `pysdl2` package. Install the library in your OS's standard location. On Windows, you can alternatively place `sdl2.dll` in the `pcbasic\lib` directory.

To use the text-based interfaces, you will need the [ANSI|pipe](http://github.com/robhagemans/ansipipe/releases) library `winsi.dll`.
Place the DLL in the `pcbasic\lib` directory.


#### External tools ####
PC-BASIC employs the following external command-line tools, if available:

| Tool                                      | OS                | Status      | Used for
|-------------------------------------------|-------------------|-------------|---------------------------------
| `notepad.exe`                             | Windows           | essential   | printing
| `lpr`                                     | Mac, Linux, Unix  | essential   | printing
| `paps`                                    | Mac, Linux, Unix  | recommended | improved Unicode support for printing
| `pbcopy`  and  `pbpaste`                  | Mac               | optional    | clipboard operation (PyGame interface)
| `beep`                                    | Mac, Linux, Unix  | optional    | sound in cli/text interface


#### Building from GitHub source repository ####
The Python distribution of PC-BASIC contains precompiled documentation files.
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

4. Place `sdl2.dll` and `sdl2_gfx.dll` in the `pcbasic\lib` directory.  


#### Installing with PyGame ####
The preferred graphical interface is SDL2. However, a PyGame interface is also available.

The 1.9.1 release of PyGame, currently still standard on some distributions (e.g. Ubuntu 16.04 LTS),
unfortunately contains a few bugs that have been resolved in newer releases. Please use the latest
PyGame release from pygame.org, or install with `pip install pygame`.
