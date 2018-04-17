10 REM PC-BASIC test 
20 REM LOCK and UNLOCK
25 REM model built with MS-DOS 5 & GW-BASIC 3.23 on VirtualBox
30 open "errors.txt" for output as 2
35 on error goto 10000
40 open "test.dat" for output as 1
50 lock#1, 1 to 3
60 print#1, "test"
70 open "test.dat" for random as 3
80 get#3, 2
90 put#3, 4
95 put#3, 2
100 lock#3, 1 to 3
110 get#3, 2
120 put#3, 2
130 unlock#1, 1 to 2
140 unlock#1, 1 to 3
150 print#1, "test2"
160 put#3, 3
999 end
10000 print#2, err, erl
10010 resume next

