1 'test o trigger old infinite-loop bug in tiled PAINT with background
5 SCREEN 1: CLS
10 LINE (50,50)-(150,150),4,B
40 PAINT (100, 100),"ABCA",4
50 PAINT (100, 100),"B",4, "A"
60 open "output.txt" for output as 1: print#1,"ok":close

