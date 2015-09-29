### PC-BASIC ###
_A free, cross-platform emulator for the GW-BASIC family of interpreters._

PC-BASIC is a free, cross-platform interpreter for GW-BASIC, Advanced BASIC (BASICA), PCjr Cartridge Basic and Tandy 1000 GW-BASIC.
It interprets these BASIC dialects with a high degree of accuracy, aiming for bug-for-bug compatibility.
PC-BASIC emulates the most common video and audio hardware on which these BASICs used to run.
PC-BASIC runs ASCII, bytecode and protected .BAS files.
It implements floating-point arithmetic in the Microsoft Binary Format (MBF) and can therefore
read and write binary data files created by GW-BASIC.  

PC-BASIC is free and open source software released under the GPL version 3.  

See also the [PC-BASIC home page](http://robhagemans.github.io/pcbasic/).

![](https://robhagemans.github.io/pcbasic/screenshots/pcbasic.png)

----------

### Quick Start Guide ###

This quick start guide covers installation and elementary use of PC-BASIC. For more information, please refer to the [full PC-BASIC documentation](http://pc-basic.org/doc#) which covers usage, command-line options and a full [GW-BASIC language reference](http://pc-basic.org/doc#reference). This documentation is also included with the current PC-BASIC release.

If you find bugs, please report them on the [SourceForge discussion page](https://sourceforge.net/p/pcbasic/discussion/bugs/) or [open an issue on GitHub](https://github.com/robhagemans/pcbasic/issues). It would be most helpful if you could include a short bit of BASIC code that triggers the bug.


#### Installation ####
Packaged distributions can be downloaded from one of the following locations:  

- [PC-BASIC releases on GitHub](https://github.com/robhagemans/pcbasic/releases)  
- [PC-BASIC releases on SourceForge](https://sourceforge.net/projects/pcbasic/files/)  

On **Windows**:  

- run the installer  
- to start, click PC-BASIC in your Start menu  

On **OS X**:  

- mount the disk image  
- to start, double click the PC-BASIC app  

On **Linux** and **other Unix**:  

- untar the archive  
- run `sudo ./install.sh`. You may be asked to install further dependencies through your OS's package management system.  
- to start, click PC-BASIC in your Applications menu or run `pcbasic` on the command line.  

If the options above are not applicable or you prefer to install from source, please
consult [`INSTALL.md`](https://github.com/robhagemans/pcbasic/blob/master/INSTALL.md) for detailed instructions.


#### Usage essentials ####
Double-click on `pcbasic` or run `pcbasic` on the Windows, OSX or Linux command line to start in interactive mode with no program loaded.  
A few selected command-line options:  
`pcbasic PROGRAM.BAS` runs PROGRAM.BAS directly.  
`pcbasic -h` shows all available command line options.  

If you're running PC-BASIC from a GUI, you can set the required options in the configuration file instead.
The configuration file is stored in the following location:

| OS         | Configuration file  
|------------|-------------------------------------------------------------------------  
| Windows    | `%APPDATA%\pcbasic\PCBASIC.INI`  
| OS X       | `~/Library/Application Support/pcbasic/PCBASIC.INI`  
| Linux      | `~/.config/pcbasic/PCBASIC.INI`  

For example, you could include the following line in `PCBASIC.INI` to emulate IBM PCjr Cartridge Basic instead of GW-BASIC 3.23:

    preset=pcjr  


#### Basic BASIC commands ####
PC-BASIC starts in interactive mode, where you can execute BASIC statements directly.
A few essential statements:  
`SYSTEM` exits PC-BASIC.  
`LOAD "PROGRAM"` loads `PROGRAM.BAS` (but does not start it).  
`RUN` starts the currently loaded program.  

Use one of the key combinations `Ctrl+Break`, `Ctrl+Scroll Lock`, `Ctrl+C` or `F12+B`
to terminate the running program and return to interactive mode.  


#### Get BASIC programs ####
The following pages have GW-BASIC and Tandy 1000 BASIC program downloads, lots of information and further links.  

- [KindlyRat](http://www.oocities.org/KindlyRat/GWBASIC.html)'s archived geocities page has a number of classic games and utilities.  
- [PeatSoft](http://archive.is/AUm6G) provides GW-BASIC documentation, utilities and some more games.  
- [Neil C. Obremski's gw-basic.com](http://www.gw-basic.com/) has fun new games made in GW-BASIC over the last few years!  
- [Leon Peyre](http://peyre.x10.mx/GWBASIC/) has a nice collection of GW-BASIC programs, including the original IBM PC-DOS 1.1 samples and the (in)famous `DONKEY.BAS`.  
- [Brooks deForest](http://www.brooksdeforest.com/tandy1000/) provides his amazing Tandy BASIC games, all released into the public domain.  
- [TVDog's Archive](http://www.oldskool.org/guides/tvdog/) is a great source of Tandy 1000 information and BASIC programs.  
- [Phillip Bigelow](http://www.scn.org/~bh162/basic_programs.html) provides scientific programs written in GW-BASIC, as many science and engineering programs once were.  
- [Gary Peek](http://www.garypeek.com/basic/gwprograms.htm) provides miscellaneous GW-BASIC sources which he released into the public domain.  
- [S.A. Moore's Classic BASIC Games page](http://www.moorecad.com/classicbasic/index.html) has some nice pictures of retro hardware and the BASIC Games from David Ahl's classic book.  
- [Joseph Sixpack's Last Book of GW-BASIC](http://www.geocities.ws/joseph_sixpack/btoc.html) has lots of GW-BASIC office and utility programs, including the PC-CALC spreadsheet.  
- [cd.textfiles.com](http://cd.textfiles.com) has tons of old shareware, among which some good GW-BASIC games - dig around here to find some treasures...  
