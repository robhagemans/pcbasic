#### You probably don't need to read this file ####
General installation instructions for PC-BASIC can be found in `README.md`.
The instructions there cover the most common platforms and use cases. If the
options described there are not applicable or you prefer to install from source,
please consult the notes below.

#### Installation from source ####
To install from source, download the source distribution and unpack the TGZ archive.
The following packages are needed or recommended when installing PC-BASIC from source:

| Package                                                         | OS                 | Status       | Needed for
|-----------------------------------------------------------------|--------------------|--------------|----------------------------
| [Python 2.7.6](http://www.python.org/download/releases/2.7.6/)  | all                | required     |
| [PyWin32](https://sourceforge.net/projects/pywin32/)            | Windows            | required     |
| [PyXDG](http://freedesktop.org/wiki/Software/pyxdg/)            | Linux, other       | required     |
| [PyGame 1.9.1](http://www.pygame.org/download.shtml)            | all                | essential    | sound and graphics
| [NumPy](https://sourceforge.net/projects/numpy/files/)          | all                | essential    | sound and graphics
| [PySerial](https://pypi.python.org/pypi/pyserial)               | all                | recommended  | physical or emulated serial port access
| [PyParallel](https://pypi.python.org/pypi/pyserial)             | Windows, Linux     | optional     | physical parallel port access
| [Pexpect](http://pexpect.readthedocs.org/en/latest/install.html)| OSX, Linux, other  | optional     | native `SHELL`

In this list, _other_ refers to operating systems other than Windows, Linux or OSX.

On **Windows**, you should download all the required packages from the project web sites linked above.

On **OSX**, there are several versions of Python 2.7 and all downloads need to match your version and CPU architecture. It's a bit tricky, I'm afraid. The easiest option seems to be installing both Python and PyGame through MacPorts or Homebrew.

On **Linux distributions with APT or DNF** (including Debian, Ubuntu, Mint and Fedora), the install script will automatically install dependencies if it is run with root privileges.

The install script can also be used on **other Unix** systems or when not installing as root. The dependencies can often be installed through your package manager. For example, on Debian-based systems:

        sudo apt-get install python2.7 python-xdg python-pygame python-numpy python-serial python-pexpect python-parallel xsel

On Fedora:

        sudo dnf install python pyxdg pygame numpy pyserial python-pexpect xsel

On FreeBSD:

        sudo pkg install python27 py27-xdg py27-game py27-numpy py27-serial py27-pexpect xsel

Note that PyParallel is not available from the Fedora and FreeBSD repos. PyParallel does not support BSD; on Fedora, you'll need to install from source if you need access to physical parallel ports. However, since most modern machines do not actually have parallel ports, you probably don't need it. PyParallel is _not_ needed for printing to a CUPS or Windows printer.


#### Building from GitHub repository source ####
The instructions above refer to the source *distribution*, which has pre-built
documentation files and other niceties.
If you wish to use the source code as-is in the GitHub repo,
you'll need to build the docs yourself. Note that `pcbasic -h` will fail if you omit
this. Compiling the documentation requires the Python modules
[`lxml`](https://pypi.python.org/pypi/lxml/3.4.3) and [`markdown`](https://pypi.python.org/pypi/Markdown).
Of course, you'll also need [`git`](https://git-scm.com/) and all the PC-BASIC dependencies listed above.  

1. Clone the github repo

        git clone --recursive https://github.com/robhagemans/pcbasic.git

2. Compile the documentation

        python setup.py build_docs

3. Run pcbasic directly from the source directory

        python pcbasic


#### Pygame issues ####
The 1.9.1 release of PyGame, as currently distributed with Ubuntu and others, unfortunately still contains a few bugs that
have already been resolved in the upstream PyGame code. This section documents workarounds for these bugs that can be used
until a newer build of PyGame is released with major distributions.

##### X11 clipboard #####
PyGame copy & paste does not work correctly on X11-based systems.
If you run into this, install one of the [`xsel`](http://www.vergenet.net/~conrad/software/xsel/) or
[`xclip`](https://sourceforge.net/projects/xclip/)  utilities and PC-BASIC will work around the issue.

##### Joystick debugging messages ####
A few debugging messages have been left in the production code for joystick handling.
The result is an annoying stream of debug messages on the console that occurs when you use a joystick.
If this bothers you, you will need to install PyGame from source; see below.

##### Segmentation fault #####
Occasionally, you may run into a crash with the following error message:

    Fatal Python error: (pygame parachute) Segmentation Fault
    Aborted (core dumped)

Unfortunately, the only workaround that I know of is to install PyGame from current development sources.

##### Installing PyGame from current development sources #####

1. Install dependencies. These are the packages I needed on Ubuntu 15.04:

        sudo apt-get install mercurial libpython-dev python-numpy ffmpeg libsdl1.2-dev libsdl-ttf2.0-dev libsdl-font1.2-dev libsdl-mixer1.2-dev libsdl-image1.2-dev libportmidi-dev libswscale-dev libavformat-dev libftgl-dev libsmpeg-dev


2. Make a working directory for your build, change into it and get the source

        hg clone https://bitbucket.org/pygame/pygame

3. Configure

        ./configure

    The script will notify you if you're missing dependencies.

4. Compile

        make

5. Install into your `/usr/local` tree

        sudo make install

See also the [PyGame source repository on BitBucket](https://bitbucket.org/pygame/pygame/wiki/VersionControl).
