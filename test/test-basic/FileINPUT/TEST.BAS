10 REM PC-BASIC test 
20 REM INPUT from file
30 open "i", #1, "input.txt
40 open "o", #2, "output.txt
50 for i=1 to 20
60 input#1, a: write#2, a
70 next i
80 close



