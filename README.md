#### PC-BASIC 3.23 ####
_A free, cross-platform emulator for GW-BASIC, BASICA, PCjr Cartridge Basic and Tandy 1000 GW-BASIC._

PC-BASIC is an interpreter for GW-BASIC files. It runs on Windows, Mac and Linux and other 
Unix-based systems and targets full compatibility with GW-BASIC version 3.23. 
PC-BASIC can run (and convert between) ASCII, bytecode and 'protected' (encrypted) .BAS files. It 
implements floating-point arithmetic in the Microsoft Binary Format (MBF) and can therefore 
read and write binary data files created by GW-BASIC.

PC-BASIC is free and open source software released under the GPL version 3. 

See [`info/ABOUT`](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/ABOUT) for authors, [`info/COPYING`](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/COPYING) for licensing details and [`info/HELP`](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/HELP) for documentation.

If you find bugs, please report them on the [discussion page](https://sourceforge.net/p/pcbasic/discussion/bugs/). It would be most helpful if you could include a short bit of BASIC code that triggers the bug.

----------


#### Installation ####
Binary distributions are currently available for Windows XP and above, Mac OSX 10.6 and above, and Linux i386. They can be [downloaded from SourceForge](https://sourceforge.net/projects/pcbasic/files/).  
On **Windows**:  
- unzip the ZIP file  
- run `pcbasic.exe`  
On **OS X**:  
- mount the disk image  
- run `pcbasic.app`  
On **Linux**:  
- untar the TGZ file  
- run `pcbasic`  


#### Installation from source ####
Installing PC-BASIC from source requires Python 2.7, PyGame 1.9.1, NumPy, PySerial, Pexpect (on Unix), PyWin32 (on Windows) and WConio (on Windows, if you want to run the command-line interface). All of these need to be installed separately.

On Linux systems, Python 2.7 usually comes pre-installed; the other packages can often be installed through your package manager. For instance, on Ubuntu:  
`apt-get install python2.7 python-pygame python-numpy python-pexpect python-serial python-parallel`  

After that, just unpack the TGZ file in your preferred location and run `./pcbasic` from the unpacked directory.

On other operating systems, use the following links:  
- [Python 2.7.6](http://www.python.org/download/releases/2.7.6/)  
- [PyGame 1.9.1](http://www.pygame.org/download.shtml)  
- [NumPy](https://sourceforge.net/projects/numpy/files/)  
- [PySerial](https://pypi.python.org/pypi/pyserial)  
- [Pexpect](http://pexpect.readthedocs.org/en/latest/install.html) (needed on Unix only)  
- [PyWin32](https://sourceforge.net/projects/pywin32/) (needed on Windows only)  
- [WConio](http://newcenturycomputers.net/projects/wconio.html) (needed for Windows command-line interface only)

Note that there are several versions of Python 2.7 for OSX and all downloads need to match your version and CPU architecture. It's a bit tricky, I'm afraid. The easiest option seems to be installing both Python and PyGame through MacPorts or Homebrew.

PySerial and Pexpect can be left out; PC-BASIC should still work except for, respectively, serial and parallel port access and the SHELL command. Numpy can probably be left out; you will have no sound in the graphical terminal. If you're not bothered about having graphics and sound and you're on a Unix system, you could leave out PyGame and NumPy altogether to use PC-BASIC in text mode only.


#### Usage essentials ####
Double-click on `pcbasic` or run `pcbasic` on the command line to start in interactive mode with no programs.  
A few selected command-line options:  
`pcbasic PROGRAM.BAS` runs PROGRAM.BAS directly.  
`pcbasic --preset=tandy` runs PC-BASIC in Tandy-1000 mode. See below for more preset options.  
`pcbasic -h` shows all available command line options.  

In the packaged versions for Windows and OSX, no command-line options can be specified. You can set the required options in `info/PCBASIC.INI` instead.


#### Basic BASIC commands ####
PC-BASIC 3.23 starts in interactive mode, where you can execute BASIC statements directly. 
A few essential statements:  
`SYSTEM` exits PC-BASIC.  
`LOAD "PROGRAM"` loads `PROGRAM.BAS` but does not start it.  
`RUN` starts the currently loaded program.  
`RUN "PROGRAM"` loads and starts `PROGRAM.BAS`.  

A PC-BASIC program called `INFO.BAS` is included on the virtual `@:` drive with more information on usage. Type `RUN "@:INFO"` in interactive mode to access it.


#### GW-BASIC, Tandy-1000 and PCjr modes ####
By default, PC-BASIC emulates GW-BASIC on a system with EGA video capabilities. The emulation target can be changed by selecting one of the following presets with the `preset` option:
`cga` GW-BASIC with CGA graphics, including composite colourburst mode.  
`pcjr` IBM PCjr Cartridge BASIC, including PCjr video and 3-voice sound capabilities and extended BASIC syntax.  
`tandy` Tandy-1000 GW-BASIC, including Tandy video and 3-voice sound capabilities and extended BASIC syntax.  


#### BASIC language reference ###
A full CC-licensed [GW-BASIC language reference](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/HELP) is included with PC-BASIC 3.23. You can find it in the `info/` directory as a text file called `HELP`; access it through your favourite text reader or through `RUN "@:INFO"`, option `Docs`. This documentation aims to document the actual behaviour of GW-BASIC 3.23, on which PC-BASIC 3.23 is modelled. Please note that the original Microsoft help file, which can be found on the internet, is rather hit-and-miss; GW-BASIC often behaves differently than documented by Microsoft. 


#### .BAS files ####
Many BASIC dialects use the same extension `.BAS`, but their files are not compatible. 
PC-BASIC runs GW-BASIC files only. Some tips to recognise GW-BASIC files:  
- ASCII files are plain text with line numbers.  
- Bytecode files start with magic byte `FF`.  
- Protected files start with magic byte `FE`.  

In particular, QBASIC files (which have no line numbers) and QuickBASIC files (magic byte `FC`) will not run. 


#### Security ####
PC-BASIC does not attempt to sandbox its programs in any way. BASIC programs have full access to your operating system - indeed, through the SHELL command, they have exactly the same capabilities as scripts or binaries run on the command line. You should treat them with the same caution as you would shell scripts or binaries. Therefore, do not run a program from the internet that you have not inspected first using LIST or one of the command line conversion options. You wouldn't just download an executable fom the internet and run it either, right?


#### MS-DOS style 8.3 file names ####
On Windows, PC-BASIC will work with the short file names provided by the operating system.
On other operating systems, more than one file may match the specified 8.3 file name. PC-BASIC will first look for a file with the exact name as specified (e.g. `FileNameCreating.ExtraDifficulties`). If this does not exist, it will look for the file name truncated to all-caps 8.3 format (`FILENAME.EXT`); if that does not exist, it will look for variants that have the same 8.3 format - e.g. `filename.EXT`, `fIlEnAmEtHaTsQuItE.eXtRaOrDiNaRy` etcetera - in lexicographic order.
If the name contains no dot (e.g. `FileName`), it will first try `FileName`, then `FILENAME`, then all case variants, and finally `FILENAME.BAS` and its case variants.



#### Newline conventions ####
In default mode, PC-BASIC will accept both DOS and Unix newline conventions. This behaviour is different from GW-BASIC, which only accepts text files in DOS format (CR/LF line endings, ctrl-Z at end-of-file). In exceptional cases, correct GW-BASIC ASCII files will not be loaded correctly, in particular if they contain LF characters followed by a number. If you encounter such a case, use the `--strict-newline` option. 
In `--strict-newline` mode, ASCII files in standard UNIX format (LF line endings, no EOF character) will fail to load: on Linux or Mac, use a utility such as [`unix2dos`](http://waterlan.home.xs4all.nl/dos2unix.html) to convert programs saved as text files before loading them. When saving as ASCII, PC-BASIC always uses the DOS conventions.


#### Text terminals ####
On Linux, in addition to the default graphical terminal, you can get a text terminal by running with the `-b` command-line option, and a curses-style terminal with the `-t` option. You can even get sound on the text terminal if you install the `beep` utility, but please be aware that Ubuntu blocks the pc-speaker by default using the line `blacklist pcspkr` in `/etc/modprobe.d/blacklist.conf`. Comment out that line, `apt-get install beep` and be sure to wear appropriate ear protection as the default volume level is LOUD.
The text terminal is also available on OSX and other UNIXes when using the source distribution. On Windows and when using the packaged OSX app, the text terminal is not available.

#### Free BASIC compilers and saner dialects ####
If you're starting a new project in BASIC, please consider one of the more sensible free versions of the language, such as [FreeBasic](www.freebasic.net), [QB64](http://www.qb64.net/) or [SmallBASIC](https://sourceforge.net/projects/smallbasic/). Under FreeDOS, you can use the [Bywater BASIC](https://sourceforge.net/projects/bwbasic/) interpreter. 


#### GW-BASIC links and downloads ####
[Norman De Forest's description of the tokenised file format](http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html) is where this project started.  
[Dan Vanderkam's online GW-BASIC decoder](http://www.danvk.org/wp/gw-basic-program-decoder/) was another inspiration.  

BASIC program downloads and further links can be found on the following pages.   
- [KindlyRat's geocities page](http://www.oocities.org/KindlyRat/GWBASIC.html)  
- [PeatSoft GW-BASIC documentation](http://archive.is/AUm6G)  
- [Neil C. Obremski's gw-basic.com](http://www.gw-basic.com/)  
- [Leon Peyre](http://peyre.x10.mx/GWBASIC/) has a nice collection of GW-BASIC programs including the original IBM PC-DOS 1.1 samples - with the (in)famous DONKEY.BAS!  
- [Phillip Bigelow](http://www.scn.org/~bh162/basic_programs.html)  
- [Gary Peek](http://www.garypeek.com/basic/gwprograms.htm)  
- [S.A. Moore's Classic BASIC Games](http://www.moorecad.com/classicbasic/index.html)  
- [Joseph Sixpack's Last Book of GW-BASIC](http://www.geocities.ws/joseph_sixpack/btoc.html) has lots of GW-BASIC office and utility programs, including the PC-CALC spreadsheet.  
- [cd.textfiles.com](http://cd.textfiles.com) has tons of old shareware, among which some good GW-BASIC games. Click on the image to enter, like in the olden days. Have fun digging.  
- [Brooks deForest](http://www.brooksdeforest.com/tandy1000/)'s collection of amazing Tandy BASIC games.
- [TVDog's Archive](http://www.oldskool.org/guides/tvdog/) has lots of Tandy 1000 information and BASIC programs.





