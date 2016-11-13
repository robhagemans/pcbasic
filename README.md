### PC-BASIC ###
_A free, cross-platform emulator for the GW-BASIC family of interpreters._

PC-BASIC is a free, cross-platform interpreter for GW-BASIC, Advanced BASIC (BASICA), PCjr Cartridge Basic and Tandy 1000 GWBASIC.
It interprets these BASIC dialects with a high degree of accuracy, aiming for bug-for-bug compatibility.
PC-BASIC emulates the most common video and audio hardware on which these BASICs used to run.
PC-BASIC runs plain-text, tokenised and protected .BAS files.
It implements floating-point arithmetic in the Microsoft Binary Format (MBF) and can therefore
read and write binary data files created by GW-BASIC.  

PC-BASIC is free and open source software released under the GPL version 3.  

See also the [PC-BASIC home page](http://robhagemans.github.io/pcbasic/).

![](https://robhagemans.github.io/pcbasic/screenshots/pcbasic.png)

----------

### Quick Start Guide ###

This quick start guide covers installation and elementary use of PC-BASIC. For more information, please refer to the [full PC-BASIC documentation](http://pc-basic.org/doc#) which covers usage, command-line options and a [comprehensive GW-BASIC language reference](http://pc-basic.org/doc#reference). This documentation is also included with the current PC-BASIC release.

If you find bugs, please report them on the [SourceForge discussion page](https://sourceforge.net/p/pcbasic/discussion/bugs/) or [open an issue on GitHub](https://github.com/robhagemans/pcbasic/issues). It would be most helpful if you could include a short bit of BASIC code that triggers the bug.


#### Installation ####
Packaged distributions can be downloaded from one of the following locations:  

- [PC-BASIC releases on GitHub](https://github.com/robhagemans/pcbasic/releases)  
- [PC-BASIC releases on SourceForge](https://sourceforge.net/projects/pcbasic/files/)  

On **Windows**:  

- run the installer  
- to start, click PC-BASIC in your Start menu  

On **Mac**:  

- mount the disk image  
- to start, double click the PC-BASIC app  

On **Linux** and **other Unix**:  

- untar the archive  
- run `sudo ./install.sh`. You may be asked to install further dependencies through your OS's package management system.  
- to start, click PC-BASIC in your Applications menu or run `pcbasic` on the command line.  

If the options above are not applicable or you prefer to install from source, please
consult [`INSTALL.md`](https://github.com/robhagemans/pcbasic/blob/master/INSTALL.md) for detailed instructions.


#### BASIC survival kit ####
Click on the PC-BASIC application icon or run `pcbasic` on the Windows, OSX or Linux command
line and PC-BASIC will start in direct mode with no program loaded. The default emulation target is
GW-BASIC 3.23 on a generic IBM-compatible PC with a VGA video card.  

PC-BASIC starts in direct mode, a 1980s-style interface operated by executing
BASIC commands directly. There is no menu, nor are there any of the visual clues
that we've come to expect of modern software.  

A few essential commands to help you get around:  
`LOAD "PROGRAM"` loads the program file named `PROGRAM.BAS` into memory, but does not run it yet.  
`LIST` displays the BASIC code of the current program.  
`RUN` starts the current program.  
`SAVE "PROGRAM",A` saves the current program to a human-readable text file named `PROGRAM.BAS`.  
`NEW` immediately deletes the current program from memory.  
`SYSTEM` exits PC-BASIC immediately, discarding any unsaved program or data.  

Use one of the key combinations `Ctrl+Break`, `Ctrl+Scroll Lock`, `Ctrl+C` or `F12+B`
to interrupt a running program and return to direct mode.  


#### Location for BASIC programs ####
By default, PC-BASIC looks for programs in your home folder.  

- On **Windows**, this is usually a folder with your user name, located under `C:\Users\`. You can find this folder in Windows Explorer by typing `%USERPROFILE%` in the address bar.
- On **Mac** and **Linux** this is the directory `~/`.

See [the documentation on accessing your drives](http://pc-basic.org/doc#mounting) for more information.


#### Configuration ####
You can supply options to change PC-BASIC's behaviour by editing the configuration file. If you install the Windows package, the installer will automatically create a shortcut to this file in the PC-BASIC start menu folder. The file can also be found in the following location:

| OS         | Configuration file  
|------------|-------------------------------------------------------------------------  
| Windows    | `%APPDATA%\pcbasic\PCBASIC.INI`  
| Mac        | `~/Library/Application Support/pcbasic/PCBASIC.INI`  
| Linux      | `~/.config/pcbasic/PCBASIC.INI`  

For example, to start with the emulation target set to Tandy 1000 GW-BASIC, include the following line under `[pcbasic]` in the configuration file:

    preset=tandy

A default configuration file will be created the first time you run PC-BASIC. See the comments in that file or consult the [documentation](http://pc-basic.org/doc#settings) for more information and example options.

If you start PC-BASIC from the command prompt (on Windows this is the `C:\>` prompt), you can supply configuration options directly. For example:  

`pcbasic PROGRAM.BAS` runs the program file named `PROGRAM.BAS` directly.  
`pcbasic --preset=tandy` starts with the emulation target set to Tandy GW-BASIC on a Tandy 1000.  
`pcbasic --preset=pcjr` starts with the emulation target set to Cartridge BASIC on an IBM PCjr.  
`pcbasic -h` shows all available command line options.  

If you use PC-BASIC from the command prompt on Windows, make sure you run the `pcbasic.com` binary. You will not see any output if you call the `pcbasic.exe` binary.

#### Getting programs ####
The following pages have GW-BASIC program downloads, lots of information and further links.  

- [KindlyRat](http://www.oocities.org/KindlyRat/GWBASIC.html)'s archived Geocities page has a number of classic games and utilities.  
- [PeatSoft](http://archive.is/AUm6G) provides GW-BASIC documentation, utilities and some more games.  
- [Neil C. Obremski's gw-basic.com](http://www.gw-basic.com/) has some fun new games made recently in GW-BASIC.  
- [Leon Peyre](http://peyre.x10.mx/GWBASIC/) has a nice collection of GW-BASIC programs, including the (in)famous first IBM PC game `DONKEY.BAS`.  
- [Brooks deForest](http://www.brooksdeforest.com/tandy1000/) provides his amazing Tandy GW-BASIC games, all released into the public domain.  
- [TVDog's Archive](http://www.oldskool.org/guides/tvdog/) is a great source of information and GW-BASIC programs for the Tandy 1000.  
- [Phillip Bigelow](http://www.scn.org/~bh162/basic_programs.html) provides scientific programs written in GW-BASIC.  
- [Gary Peek](http://www.garypeek.com/basic/gwprograms.htm) provides miscellaneous GW-BASIC sources which he released into the public domain.  
- [S.A. Moore's Classic BASIC Games page](http://www.moorecad.com/classicbasic/index.html) provides the BASIC games from David Ahl's classic book.  
- [Joseph Sixpack's Last Book of GW-BASIC](http://www.geocities.ws/joseph_sixpack/btoc.html) has lots of office and utility programs, including the PC-CALC spreadsheet.  
- [Thomas C. McIntyre](https://web.archive.org/web/20060410121551/http://scottserver.net/basically/geewhiz.html)'s GeeWhiz Collection has business applications, games and reference material.
- [cd.textfiles.com](http://cd.textfiles.com) has tons of old shareware, among which some good GW-BASIC games.  
