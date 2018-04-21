10 key off: width 40
15 open "output.txt" for output as 1
20 M$ = space$(40)
30 locate 25,1: print m$: locate 10,10
35 print#1, 1
40 M$ = space$(41)
50 locate 25,1: print m$: locate 10,10
60 print#1, 2
70 close
