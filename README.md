#### PC-BASIC 3.23 ####
_A free, cross-platform emulator for GW-BASIC, BASICA, PCjr Cartridge Basic and Tandy 1000 GW-BASIC._

PC-BASIC is an interpreter for GW-BASIC programs. It runs on Windows, Mac and Linux and other 
Unix-based systems and targets full compatibility with GW-BASIC version 3.23. 
PC-BASIC can run (and convert between) ASCII, bytecode and 'protected' (encrypted) .BAS files. It 
implements floating-point arithmetic in the Microsoft Binary Format (MBF) and can therefore 
read and write binary data files created by GW-BASIC.

PC-BASIC is free and open source software released under the GPL version 3. 

See [`info/ABOUT`](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/ABOUT) for authors, [`info/COPYING`](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/COPYING) for licensing details,
[`info/USAGE`](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/USAGE) for usage essentials and [`info/HELP`](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/HELP) for BASIC language documentation.

If you find bugs, please report them on the SourceForge discussion page at [https://sourceforge.net/p/pcbasic/discussion/bugs/](https://sourceforge.net/p/pcbasic/discussion/bugs/). It would be most helpful if you could include a short bit of BASIC code that triggers the bug.

----------


#### Installation ####
Binary distributions are currently available for Windows XP and above, Mac OSX 10.6 and above, and Linux on i386 architecture. They can be downloaded from SourceForge at [https://sourceforge.net/projects/pcbasic/files/](https://sourceforge.net/projects/pcbasic/files/).  

On **Windows**:  
- unzip the ZIP file  
- run `pcbasic.exe`  

On **OS X**:  
- mount the disk image  
- run `pcbasic.app`  

On **Linux**:  
- untar the TGZ file  
- run `pcbasic`  


#### Using the source distribution ####
If you prefer to use PC-BASIC from source you should install the following dependencies:

- [Python 2.7.6](http://www.python.org/download/releases/2.7.6/)  
- [PyGame 1.9.1](http://www.pygame.org/download.shtml)  
- [NumPy](https://sourceforge.net/projects/numpy/files/)  
- [PySerial](https://pypi.python.org/pypi/pyserial)  
- [Pexpect](http://pexpect.readthedocs.org/en/latest/install.html) (needed on Unix only)  
- [PyWin32](https://sourceforge.net/projects/pywin32/) (needed on Windows only)  
- [WConio](http://newcenturycomputers.net/projects/wconio.html) (needed for Windows command-line interface only)  

Of these, only Python is mandatory; however, without the optional dependencies functionality will be limited.
After installing the dependencies, unpack the TGZ archive and run the `pcbasic` script with Python. 

On **Linux** systems, Python 2.7 usually comes pre-installed; the other packages can often be installed through your package manager. For example, on Ubuntu you can install all dependencies at once through APT:  
`sudo apt-get install python2.7 python-pygame python-numpy python-pexpect python-serial python-parallel`  

On **OSX** systems, there are several versions of Python 2.7 and all downloads need to match your version and CPU architecture. It's a bit tricky, I'm afraid. The easiest option seems to be installing both Python and PyGame through MacPorts or Homebrew.


#### Usage essentials ####
Double-click on `pcbasic` or run `pcbasic` on the command line to start in interactive mode with no programs.  
A few selected command-line options:  
`pcbasic PROGRAM.BAS` runs PROGRAM.BAS directly.  
`pcbasic -h` shows all available command line options.  

By default, PC-BASIC emulates GW-BASIC on a system with VGA video capabilities. The emulation target can be changed by selecting one of the following presets with the `preset` option:  
`pcbasic --preset=cga` GW-BASIC with CGA graphics, including composite colourburst mode.  
`pcbasic --preset=pcjr` IBM PCjr Cartridge BASIC, including PCjr video and 3-voice sound capabilities and extended BASIC syntax.  
`pcbasic --preset=tandy` Tandy-1000 GW-BASIC, including Tandy video and 3-voice sound capabilities and extended BASIC syntax.  
Other available presets include `mda`, `ega`, `hercules`, `olivetti`. 

If you're running PC-BASIC from a GUI, you can set the required options in `info/PCBASIC.INI` instead.

For more information, consult the text file [`info/USAGE`](https://sourceforge.net/p/pcbasic/code/ci/master/tree/info/USAGE) or run `pcbasic -h`.


#### Basic BASIC commands ####
PC-BASIC 3.23 starts in interactive mode, where you can execute BASIC statements directly. 
A few essential statements:  
`SYSTEM` exits PC-BASIC.  
`LOAD "PROGRAM"` loads `PROGRAM.BAS` but does not start it.  
`RUN` starts the currently loaded program.  
`RUN "PROGRAM"` loads and starts `PROGRAM.BAS`.  

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
PC-BASIC follows DOS file system conventions, where files consist of a 
8-character name and 3-character extension and names are case insensitive.
Note that DOS conventions are subtly different from Windows short filename 
conventions and not-so-subtly different from Unix conventions. This may lead
to surprising effects in the presence of several files that match 
the same DOS name. To avoid such surprises, run PC-BASIC in a working 
directory of its own and limit file names to all-caps 8.3 format.

When opening a data file, PC-BASIC will first look for a file with the name 
exactly as provided. This can be a long name and will be case sensitive if
your file system is. If such a file is not found, it will truncate the name
provided to 8.3 format and convert to all uppercase. If that exact name is
not found, it will look for 8.3 names in mixed case which match the name
provided in a case-insensitive way. Such files are searched in lexicographic
order. On Windows, the name matched can be a short filename as well as a 
long filename (provided it is of 8.3 length; it may, for example, contain 
spaces).

When loading or saving a program file, no attempt is made to find an exact 
match. Instead, the search will first match the all-caps 8.3 version of the
name and continue in lexicographic order as above. If no extension is 
specified, the extension .BAS will be implicitly added. To load a program
with no extension, end the filename in a dot. On file systems without
short filenames, it is not possible to load a program if its filename is 
longer than 8.3 or ends in a dot.

The only valid path separator is the backslash `\`. 


#### Newline conventions ####
In default mode, PC-BASIC will accept both DOS and Unix newline conventions. This behaviour is different from GW-BASIC, which only accepts text files in DOS format (CR/LF line endings, ctrl-Z at end-of-file). In exceptional cases, correct GW-BASIC ASCII files will not be loaded correctly, in particular if they contain LF characters followed by a number. If you encounter such a case, use the `--strict-newline` option. 
In `--strict-newline` mode, ASCII files in standard UNIX format (LF line endings, no EOF character) will fail to load: on Linux or Mac, use a utility such as [`unix2dos`](http://waterlan.home.xs4all.nl/dos2unix.html) to convert programs saved as text files before loading them. When saving as ASCII, PC-BASIC always uses the DOS conventions.


#### Codepages and UTF-8 ####
PC-BASIC supports a large number of codepages, including double-byte character set codepages used for Chinese, Japanese and Korean. PC-BASIC will load and save all program files as if encoded in the codepage you select. It is possible to load and save in UTF-8 format, by choosing the `--utf-8` option. In `--utf-8` mode, ASCII program source will be saved and loaded in standard UTF-8 encoding. Please note that you will still need to select a codepage that provides the Unicode characters that your program needs.


#### Command-line interface ####
You can run PC-BASIC in command-line mode by running with the `-b` option. On Linux, there's also a curses-style interface available with the `-t` option. You can even get sound in the text and command-line interfaces if you install the Unix `beep` utility (if you use Ubuntu, please be aware that the pc-speaker is switched off by default. You'll need to edit `/etc/modprobe.d/blacklist.conf` and comment out the line `blacklist pcspkr`. Then, `apt-get install beep` and be sure to wear appropriate ear protection as the default volume level is LOUD.) 

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





