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

This quick start guide covers installation and elementary use of PC-BASIC. For more information, please refer to the [PC-BASIC documentation](http://pc-basic.org/doc/2.0#).

If you find bugs, please [open an issue on GitHub](https://github.com/robhagemans/pcbasic/issues). It would be most helpful if you could include a short bit of BASIC code that triggers the bug.


#### Installation ####

PC-BASIC desktop installers for Windows, Mac, and Linux can be downloaded from [GitHub](https://github.com/robhagemans/pcbasic/releases).

Python users can obtain the PC-BASIC package from [PyPI](https://pypi.org/project/pcbasic/) through `pip install pcbasic`.


#### BASIC survival kit ####
PC-BASIC has a 1980s-style interface operated by executing
typed commands. There is no menu, nor are there any of the visual clues
that we've come to expect of modern software.  

A few essential commands to help you get around:  

| Command               | Effect                                                        |
|-----------------------|---------------------------------------------------------------|
| `LOAD "PROGRAM"`      | loads the program file named `PROGRAM.BAS` into memory        |
| `LIST`                | displays the BASIC code of the current program                |
| `RUN`                 | starts the current program                                    |
| `SAVE "PROGRAM",A`    | saves the current program to a text file named `PROGRAM.BAS`  |
| `NEW`                 | immediately deletes the current program from memory           |
| `SYSTEM`              | exits PC-BASIC immediately, discarding any unsaved program    |

Use one of the key combinations `Ctrl+Break`, `Ctrl+Scroll Lock`, `Ctrl+C` or `F12+B`
to interrupt a running program.  


#### Program location ####
If started through the start-menu shortcut, PC-BASIC looks for programs in the shortcut's start-in folder. By default, this will be your home folder.

- On **Windows**, this is usually a folder with your user name, located under `C:\Users\`. You can find this folder in Windows Explorer by typing `%USERPROFILE%` in the address bar.
- On **Mac** and **Linux** this is the directory `~/`.

If started from the command prompt, PC-BASIC looks for programs in the current working directory.

See [the documentation on accessing your drives](http://pc-basic.org/doc/2.0#mounting) for more information.


#### External resources ####
The following pages have GW-BASIC program downloads, lots of information and further links.  

- [KindlyRat](http://www.oocities.org/KindlyRat/GWBASIC.html)'s archived Geocities page has a number of classic games and utilities.  
- [PeatSoft](http://archive.is/AUm6G) provides GW-BASIC documentation, utilities and some more games.  
- [Neil C. Obremski's gw-basic.com](http://www.gw-basic.com/) has some fun new games made recently in GW-BASIC.  
- [Leon Peyre](http://peyre.x10.mx/GWBASIC/) has a nice collection of GW-BASIC programs, including the (in)famous first IBM PC game `DONKEY.BAS`.  
- [Brooks deForest](https://web.archive.org/web/20170222075609/brooksdeforest.com/tandy1000) provides his amazing Tandy GW-BASIC games, all released into the public domain.  
- [TVDog's Archive](http://www.oldskool.org/guides/tvdog/) is a great source of information and GW-BASIC programs for the Tandy 1000.  
- [Phillip Bigelow](http://www.scn.org/~bh162/basic_programs.html) provides scientific programs written in GW-BASIC.  
- [Gary Peek](http://www.garypeek.com/basic/gwprograms.htm) provides miscellaneous GW-BASIC sources which he released into the public domain.  
- [S.A. Moore's Classic BASIC Games page](http://www.moorecad.com/classicbasic/index.html) provides the BASIC games from David Ahl's classic book.  
- [Joseph Sixpack's Last Book of GW-BASIC](http://www.geocities.ws/joseph_sixpack/btoc.html) has lots of office and utility programs, including the PC-CALC spreadsheet.  
- [Thomas C. McIntyre](https://web.archive.org/web/20060410121551/http://scottserver.net/basically/geewhiz.html)'s GeeWhiz Collection has business applications, games and reference material.
- [cd.textfiles.com](http://cd.textfiles.com) has tons of old shareware, among which some good GW-BASIC games.  
