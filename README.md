### PC-BASIC ###
_A free, cross-platform emulator for legacy Microsoft BASIC applications._

PC-BASIC is a free, cross-platform interpreter for GW-BASIC, BASICA, PCjr Cartridge Basic and Tandy 1000 GW-BASIC.
It interprets these BASIC dialects with a high degree of accuracy, aiming for bug-for-bug compatibility. PC-BASIC emulates the most common video and audio hardware supported in their time. PC-BASIC can run (and convert between) ASCII, bytecode and 'protected' (encrypted) .BAS files. It implements floating-point arithmetic in the Microsoft Binary Format (MBF) and can therefore 
read and write binary data files created by GW-BASIC.  

PC-BASIC is free and open source software released under the GPL version 3.  

See also the [PC-BASIC home page](http://robhagemans.github.io/pcbasic/).

----------

### Quick Start Guide ###

This quick start guide covers installation and elementary use of PC-BASIC. For more information, please refer to the [full PC-BASIC documentation](http://robhagemans.github.io/pcbasic/doc/) for usage, command-line options and a full GW-BASIC language reference. This documentation is also included with the current PC-BASIC release.

If you find bugs, please report them on the SourceForge discussion page at [https://sourceforge.net/p/pcbasic/discussion/bugs/](https://sourceforge.net/p/pcbasic/discussion/bugs/). It would be most helpful if you could include a short bit of BASIC code that triggers the bug.

#### Installation ####
Packaged distributions are currently available for Windows XP and above, Mac OSX 10.6 and above, and Linux on 32-bit or 64-bit Intel/AMD architecture. 

They can be downloaded from one of the following locations:  
- GitHub at [https://github.com/robhagemans/pcbasic/releases](https://github.com/robhagemans/pcbasic/releases).  
- SourceForge at [https://sourceforge.net/projects/pcbasic/files/](https://sourceforge.net/projects/pcbasic/files/).  

On **Windows**:  
- run the installer  
- to start, click the PC-BASIC 3.23 item in your Start menu.

On **OS X**:  
- mount the disk image  
- move `PC-BASIC.app` to your Applications folder  
- to start, double click the PC-BASIC app  

On **Linux**:  
- untar the archive  
- run `sudo ./install.sh`  
- to start, click the PC-BASIC 3.23 item in your Applications menu (or run `pcbasic` on the command line).  

#### Installation from source ####
If your system is not supported or you prefer to install from source, download the source distribution and unpack the TGZ archive. You should also make sure you have the required dependencies installed (see below).

If you want, you can run the Python script `pcbasic` straight from the unpacked directory. On **Unix-like systems**, you also have the option to install PC-BASIC to a dedicated directory and create FreeDesktop menu items using the `install.sh` shell script. Run with root privileges if you wish to install to a system-wide directory and be able to access `pcbasic` from anywhere.

#### Source dependencies ####
The following packages are needed or recommended when installing PC-BASIC from source:

| Package                                                         | OS      | Status       | Notes  
|-----------------------------------------------------------------|---------|--------------|----------------------------  
| [Python 2.7.6](http://www.python.org/download/releases/2.7.6/)  | all     | required     |   
| [PyWin32](https://sourceforge.net/projects/pywin32/)            | Windows | required     |  
| [PyGame 1.9.1](http://www.pygame.org/download.shtml)            | all     | essential    | for sound and graphics  
| [NumPy](https://sourceforge.net/projects/numpy/files/)          | all     | essential    | for sound and graphics  
| [PySerial](https://pypi.python.org/pypi/pyserial)               | all     | recommended  | for serial/parallel port access  
| [Pexpect](http://pexpect.readthedocs.org/en/latest/install.html)| Unix    | optional     | for native `SHELL`  

Note that the official Pygame release 1.9.1 has a bug in its handling of copy & paste on X11-based systems.
If you run into this, install one of the [`xsel`](http://www.vergenet.net/~conrad/software/xsel/) or [`xclip`](https://sourceforge.net/projects/xclip/)  utilities and PC-BASIC will work around the issue.  

On **Linux** systems, Python 2.7 usually comes pre-installed; the other packages can often be installed through your package manager. For example, on Ubuntu you can install all dependencies at once through APT:  
`sudo apt-get install python2.7 python-pygame python-numpy python-pexpect python-serial python-parallel xsel`  

On **OSX** systems, there are several versions of Python 2.7 and all downloads need to match your version and CPU architecture. It's a bit tricky, I'm afraid. The easiest option seems to be installing both Python and PyGame through MacPorts or Homebrew.

On **Windows** systems, you should download all the required packages from the project web sites linked above.


#### Usage essentials ####
Double-click on `pcbasic` or run `pcbasic` on the command line to start in interactive mode with no programs.  
A few selected command-line options:  
`pcbasic PROGRAM.BAS` runs PROGRAM.BAS directly.  
`pcbasic -h` shows all available command line options.  

If you're running PC-BASIC from a GUI, you can set the required options in the configuration file instead. The configuration file is a file named `PCBASIC.INI`, stored in the following location:

| OS         | Configuration file location  
|------------|-------------------------------------------------------------------------  
| Windows XP | `C:\Documents and Settings\` (your username) `\Application Data\pcbasic`  
| Windows 7  | `C:\Users\` (your username) `\AppData\Roaming\pcbasic`  
| OS X       | `~/Library/Application Support/pcbasic`   
| Linux      | `~/.config/pcbasic`  

For example, you could include the following line in `PCBASIC.INI` to emulate IBM PCjr Cartridge Basic instead of GW-BASIC 3.23:

    preset=pcjr  


For a full list of options, run `pcbasic -h`.


#### Basic BASIC commands ####
PC-BASIC starts in interactive mode, where you can execute BASIC statements directly. 
A few essential statements:  
`SYSTEM` exits PC-BASIC.  
`LOAD "PROGRAM"` loads `PROGRAM.BAS` but does not start it.  
`RUN` starts the currently loaded program.  
`RUN "PROGRAM"` loads and starts `PROGRAM.BAS`.  

A full CC-licensed GW-BASIC language reference is included with PC-BASIC. This documentation aims to document the actual behaviour of GW-BASIC 3.23, on which PC-BASIC is modelled. Please note that the original Microsoft help file, which can be found on the internet, is rather hit-and-miss; GW-BASIC often behaves differently than documented by Microsoft. 


#### Free BASIC compilers and saner dialects ####
If you're starting a new project in BASIC, please consider one of the more sensible free versions of the language, such as [FreeBasic](www.freebasic.net), [QB64](http://www.qb64.net/) or [SmallBASIC](https://sourceforge.net/projects/smallbasic/). Under FreeDOS, you can use the [Bywater BASIC](https://sourceforge.net/projects/bwbasic/) interpreter. 


#### GW-BASIC links and downloads ####
[Norman De Forest's description of the tokenised file format](http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html) is where this project started.  
[Dan Vanderkam's online GW-BASIC decoder](http://www.danvk.org/wp/gw-basic-program-decoder/) was another inspiration.  

BASIC program downloads and further links can be found on the following pages.   
- [KindlyRat's geocities page](http://www.oocities.org/KindlyRat/GWBASIC.html)  
- [PeatSoft GW-BASIC documentation](http://archive.is/AUm6G)  
- [Neil C. Obremski's gw-basic.com](http://www.gw-basic.com/)  
- [Leon Peyre](http://peyre.x10.mx/GWBASIC/) has a nice collection of GW-BASIC programs including the original IBM PC-DOS 1.1 samples and the (in)famous DONKEY.BAS  
- [Phillip Bigelow](http://www.scn.org/~bh162/basic_programs.html)  
- [Gary Peek](http://www.garypeek.com/basic/gwprograms.htm)  
- [S.A. Moore's Classic BASIC Games](http://www.moorecad.com/classicbasic/index.html)  
- [Joseph Sixpack's Last Book of GW-BASIC](http://www.geocities.ws/joseph_sixpack/btoc.html) has lots of GW-BASIC office and utility programs, including the PC-CALC spreadsheet.  
- [cd.textfiles.com](http://cd.textfiles.com) has tons of old shareware, among which some good GW-BASIC games. Click on the image to enter, like in the olden days. Have fun digging.  
- [Brooks deForest](http://www.brooksdeforest.com/tandy1000/)'s collection of amazing Tandy BASIC games.  
- [TVDog's Archive](http://www.oldskool.org/guides/tvdog/) has lots of Tandy 1000 information and BASIC programs.  





