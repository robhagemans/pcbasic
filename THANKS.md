## Acknowledgements

### Contributors

PC-BASIC would not exist without those contributing code, reporting bugs,
sending in patches, and documenting GW-BASIC's behaviour. Thank you all!

- **Rob Hagemans**,   lead author
- **Wengier Wu**,     bug fixes, advice for CJK support
- **WJB**,            bug fixes
- **Ronald Herrera**, testing, bug hunting
- **Miguel Dorta**,   testing, serial ports
- **Patrik**,         testing, serial ports
- **Duane**,          testing, serial ports


### Shoulders of Giants

PC-BASIC depends on the following open-source projects:

  * [Python](http://www.python.org)
  * [Simple DirectMedia Layer (SDL)](http://www.libsdl.org)
  * [PySDL2](https://pysdl2.readthedocs.org/en/latest/)
  * [NumPy](http://www.numpy.org)
  * [Python for Windows Extensions (PyWin32)](https://sourceforge.net/projects/pywin32/)
  * [PySerial](http://pyserial.sourceforge.net/pyserial.html)
  * [PExpect](http://pexpect.readthedocs.org/en/latest/)
  * [ANSI|pipe](https://github.com/robhagemans/ansipipe)


### Fond memories

PC-BASIC would not have been what it is without the following open-source projects
which it has depended on in the past:

  * [PyGame](http://www.pygame.org)
  * **Tom Rothamel**'s [PyGame Subset for Android](https://web.archive.org/web/20150712040220/http://pygame.renpy.org/) (superseded by [RAPT](http://www.renpy.org/doc/html/android.html))


### Technical Documentation

Building PC-BASIC would have been impossible without the immense amounts of
technical documentation that has been made available online. It has proven not
to be feasible to compile a complete list of the documentation used. Many
thanks to all those who make technical information freely available, and
apologies to those whose contribution I have failed to acknowledge here.

##### GW-BASIC tokenised file format

  * **Norman De Forest**'s seminal [documentation of GW-BASIC tokens](http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html).
    _This documentation was the starting point for the development of PC-BASIC._
  * **Dan Vanderkam**'s [online GW-BASIC decoder](http://www.danvk.org/wp/2008-02-03/reading-old-gw-basic-programs/)

##### GW-BASIC protected file format

  * **Paul Kocher**, _The Cryptogram computer supplement_ **19**, American Cryptogram Association, Summer 1994

##### Video hardware

  * **John Elliott**'s [Vintage PC pages](http://www.seasip.info/VintagePC/)
  * **Dan Rollins**' [TechHelp](http://webpages.charter.net/danrollins/techhelp/0089.HTM) pages on PC video memory layout
  * **Great Hierophant**'s [Nerdly Pleasures Blog](http://nerdlypleasures.blogspot.com)

##### Microsoft Binary Format

  * Forum contributions by **[Julian Brucknall](http://www.boyet.com/Articles/MBFSinglePrecision.html)** and **[Adam Burgoyne](http://www.experts-exchange.com/Programming/Languages/Pascal/Delphi/Q_20245266.html)**

##### Data cassette format

  * **Mike Brutman**'s [Analysis of the IBM PC Data cassette format](http://www.brutman.com/Cassette_Waveforms/Cassette_Waveforms.html)
  * **Dan Tobias**' [IBM PC Data cassette format documentation](http://fileformats.archiveteam.org/wiki/IBM_PC_data_cassette)

##### BASICODE

  * **Janny Looyenga**'s documentation of the [BASICODE format](http://www.nostalgia8.nl/basicode.htm)
  * **Prof. Dr. Horst Völz**'s documentation of the [BASICODE cassette file format](http://www.kc85emu.de/scans/rfe0190/Basicode.htm)

##### Technical information on many topics

  * [VOGONS](http://www.vogons.org/)
  * **Erik S. Klein**'s [Vintage computer forums](http://www.vintage-computer.com)
  * **Peter Berg**'s [Pete's QBasic/QuickBasic site](http://www.petesqbsite.com/)

### Fonts

  * **Henrique Peron**'s [CPIDOS codepage pack](http://www.freedos.org/software/?prog=cpidos)
  * **Dmitry Bolkhovityanov**'s [Uni-VGA font](http://www.inp.nsk.su/~bolkhov/files/fonts/univga/)
  * **Roman Czyborra**, **Qianqian Fang** and others' [GNU UniFont](https://savannah.gnu.org/projects/unifont)
  * [DOSBox](http://www.dosbox.com) VGA fonts
  * **Andries Brouwer**'s [CPI font file format documentation](http://www.win.tue.nl/~aeb/linux/kbd/font-formats-3.html)

### Unicode-codepage mappings

  * [The Unicode Consortium and contributors](http://www.unicode.org/Public/MAPPINGS/VENDORS)
  * [GNU libiconv Project](https://www.gnu.org/software/libiconv/)
  * [Aivosto](http://www.aivosto.com/vbtips/charsets-codepages.html)
  * **Konstantinos Kostis**' [Charsets Index](http://www.kostis.net/charsets/)
  * [IBM CDRA](http://www-01.ibm.com/software/globalization/cdra/)
  * **Masaki Tojo**'s [Camellia](https://github.com/mtojo/camellia)

### Bibliography

  * _GW-BASIC 3.23 User's Guide_, Microsoft Corporation, 1987.
  * _IBM Personal Computer Hardware Reference Library: BASIC_, IBM, 1982.
  * _Tandy 1000 BASIC, A Reference Guide_, Tandy Corporation.
  * **William Barden, Jr.**, _Graphics and Sound for the Tandy 1000s and PC Compatibles_, Microtrend, 1987.
  * **Don Inman** and **Bob Albrecht**, _The GW-BASIC Reference_, Osborne McGraw-Hill, 1990.
  * **Thomas C. McIntyre**, _BLUE: BASIC Language User Essay_, 1991, [available online](https://web.archive.org/web/20060410121551/http://scottserver.net/basically/geewhiz.html).

### Development tools

PC-BASIC is developed using [Git](https://git-scm.com/) source control,
[GEdit](https://wiki.gnome.org/Apps/Gedit) and [Atom](https://atom.io/) text
editors on an [Ubuntu](http://www.ubuntu.com/) Linux system and hosted on
[GitHub](https://github.com/) and [SourceForge](https://sourceforge.net/).

Packaging and documentation depends on the following projects:

  * [PyInstaller](http://www.pyinstaller.org)
  * [Nullsoft Scriptable Install System](http://nsis.sourceforge.net)
  * [7-Zip](http://www.7-zip.org)
  * [The GNU Base System](http://www.gnu.org/)
  * [LXML](http://lxml.de)
  * [Markdown](https://pypi.python.org/pypi/Markdown)


### Emulators

These excellent emulators have been indispensable tools in documenting the
behaviour of various Microsoft BASIC dialects.

  * [DOSBox](http://www.dosbox.com)
  * [MESS](http://www.mess.org)
  * [PCE PC Emulator](http://www.hampa.ch/pce/)
