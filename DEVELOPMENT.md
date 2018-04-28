

### Setting up a development environment for PC-BASIC
These instructions cover the steps needed to install the development source of PC-BASIC and its dependencies. You can also follow them if you simply want to install PC-BASIC from the source repository on GitHub.

#### You won't need to read this file just to install PC-BASIC ####
General installation instructions for PC-BASIC can be found in `README.md`.
The instructions there cover the most common platforms and use cases.


#### Dependencies ####
The following packages are needed or recommended when installing PC-BASIC:

| Package                                                                   | OS                 | Status       | Used for
|---------------------------------------------------------------------------|--------------------|--------------|----------------------------------------
| [Python 2.7.12](https://www.python.org/downloads/release/python-2712/)    | all                | required     |
| [Setuptools](https://pypi.python.org/pypi/setuptools)                     | all                | required     |
| [SDL2](https://www.libsdl.org/download-2.0.php)                           | all                | recommended  | sound and graphics
| [NumPy](https://sourceforge.net/projects/numpy/files/)                    | all                | recommended  | sound and graphics
| [PySerial 3.4](https://pypi.python.org/pypi/pyserial)                     | all                | optional     | physical or emulated serial port access
| [PyParallel 0.2](https://pypi.python.org/pypi/pyparallel)                 | Windows, Linux     | optional     | physical parallel port access
| [PyGame 1.9.3](http://www.pygame.org)                                     | all                | optional     | sound and graphics (PyGame interface)
| [PyAudio](http://people.csail.mit.edu/hubert/pyaudio/)                    | all                | experimental | sound (PortAudio engine)


`setuptools` and `pip` are included with Python.
Once you have a working Python installation, most dependencies can be installed with `pip`:

        pip install pysdl2 numpy pygame pyaudio pyserial pyparallel

To use the graphical interface, you will also need to install the [SDL2](https://www.libsdl.org/download-2.0.php) library.
Install the library in your OS's standard location. On Windows, you can alternatively place `sdl2.dll` in the `pcbasic\lib` directory.

PyParallel is only needed to access physical parallel ports, not for printing to a CUPS or Windows printer.
Note that most modern machines do not actually have parallel ports.



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
The following additional packages are used for development, testing and packaging:

| Package                                                                                                        | OS                | Used for
|----------------------------------------------------------------------------------------------------------------|-------------------|-----------------
| [Git](https://git-scm.com/)                                                                                  | all               | development
| [Microsoft Visual C++ Compiler for Python 2.7](https://www.microsoft.com/en-us/download/details.aspx?id=44266) | Windows           | development
| [`lxml`](https://pypi.python.org/pypi/lxml/3.4.3)                                                              | all               | documentation
| [`markdown`](https://pypi.python.org/pypi/Markdown)                                                            | all               | documentation
| [Prince](https://www.princexml.com/download/)                                                                | all               | documentation
| [`pylint`](https://pypi.python.org/pypi/pylint/1.7.6)                                                          | all               | testing
| [`coverage`](https://pypi.python.org/pypi/coverage)                                                            | all               | testing
| [`cx_Freeze`](https://pypi.org/project/cx_Freeze/)                                                             | Windows, MacOS    | packaging
| [`fpm`](https://github.com/jordansissel/fpm)                                                                   | Linux             | packaging


These are the steps to set up the local repository ready to run PC-BASIC:

1. Clone the repo from GitHub

        git clone --recursive https://github.com/robhagemans/pcbasic.git

2. Compile the documentation

        python setup.py build_docs

3. Windows only: compile the `win32_console` extension

        python setup.py build_ext --inplace

4. Run pcbasic directly from the source directory

        python -m pcbasic


#### Windows console notes ####
When using PC-BASIC with a text-based interface on Windows, please note:
- You need to set the console font to one of the TrueType fonts, for example Lucida Console.
  The default raster font will not display non-ASCII letters correctly.

- If the Windows console codepage is set to 65001, strange errors may occur when using `pcbasic -n` or the
  Session API through standard I/O. For example, `IOError: [Errno 0] Error`.
  This is a [known issue](https://bugs.python.org/issue1602) with
  Python 2.7 and Windows. There is no fix; to work around it, change to another console codepage.


#### Building `SDL2_gfx.dll` on Windows ###
The [SDL2_gfx](http://www.ferzkopp.net/wordpress/2016/01/02/sdl_gfx-sdl2_gfx/) plugin is needed if
you want to use the SDL2 interface with smooth scaling. Most Linux distributions will include this with their pysdl2 package.
On Windows, you will need to compile from source. To compile from the command line with Microsoft Visual C++ for Python 2.7:

1. Download and unpack the SDL2 development package for Visual C++ `SDL2-devel-2.x.x-VC.zip` and the SDL2_gfx source code archive.

2. Compile with the following options (for 64-bit):

        cl /LD /D_WIN32 /DWINDOWS /D_USRDLL /DDLL_EXPORT /Ipath_to_unpacked_sdl2_archive\include *.c /link path_to_unpacked_sdl2_archive\lib\x64\sdl2.lib /OUT:SDL2_gfx.dll

   or for 32-bit:

        cl /LD /D_WIN32 /DWINDOWS /D_USRDLL /DDLL_EXPORT /Ipath_to_unpacked_sdl2_archive\include *.c /link path_to_unpacked_sdl2_archive\lib\x86\sdl2.lib /OUT:SDL2_gfx.dll

Those who prefer to use the [MinGW](http://mingw.org/) GCC compiler, follow these steps:  

1. Download and unpack the SDL2 binary, the SDL2 development package for MinGW and the SDL2_gfx source code archive. Note that the SDL2 development package contains several subdirectories for different architectures. You'll need the 32-bit version in `i686-w64-mingw32/`  

2. Place `SDL2.dll` in the directory where you unpacked the SDL2_gfx source code.  

3. In the MinGW shell, run  

        ./autogen.sh
        ./configure --with-sdl-prefix="/path/to/where/you/put/i686-w64-mingw32/"
        make
        gcc -shared -o SDL2_gfx.dll *.o SDL2.dll


#### Installing with PyGame ####
The preferred graphical interface is SDL2. However, a PyGame interface is also available.

The 1.9.1 release of PyGame, currently still standard on some distributions (e.g. Ubuntu 16.04 LTS),
unfortunately contains a few bugs that have been resolved in newer releases. Please use the latest
PyGame release from pygame.org, or install with `pip install pygame`.

#### Contributing code ####

The current code base of PC-BASIC was written by a single author, Rob Hagemans.
That is not to say it should stay that way. If you would like to contribute
code to PC-BASIC, please contact the author at _robhagemans@users.sourceforge.net_.

You'll need to agree for your code contributions to be licensed under the [Expat MIT License](https://opensource.org/licenses/MIT).
This is a more permissive licence than PC-BASIC is (currently) released under. The reason I ask for
a permissive licence for contributions is that it allows me to re-license the code at a later date.
