5 REM test GET and PUT in Tandy SCREEN 6
6 REM note that width of the sprite is double that indicated
10 CLEAR,,,32768!:SCREEN 6
20 DIM X(1000),Y(1000)
30 CLS:KEY OFF:LOCATE 1,1
40 PRINT"ABCD"
50 GET (0,0)-(7,7),X
60 CLS
70 PUT (320,0),X
100 DEF SEG=&hb800
110 REM omitting 4th & 8th interlaced scan line as DOSBOX seems to have a bug showing garbage there
120 BSAVE "output.bsv", 0, 24000
130 CLS
140 BLOAD "output.bsv":LOCATE 10,1

