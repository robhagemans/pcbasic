10 REM PC-BASIC test 
20 REM errors in file expressions
30 on error goto 1000
40 open "output.txt" for output as 1
50 print#1, varptr(#0
52 print#1, varptr(#1
54 print#1, varptr(#4
60 print#1, varptr(#0)
62 print#1, varptr(#1)
64 print#1, varptr(#4)
70 print#1, ioctl$(#0
72 print#1, ioctl$(#1
74 print#1, ioctl$(#4
80 print#1, input$(1, #0
82 print#1, input$(1, #1
84 print#1, input$(1, #4
90 print#1, input$(1, #0)
92 print#1, input$(1, #1)
94 print#1, input$(1, #4)
100 print#1, input$(1, 0
102 print#1, input$(1, 1
104 print#1, input$(1, 4
110 print#1, input$(1, 0)
112 print#1, input$(1, 1)
114 print#1, input$(1, 4)
999 end
1000 print#1, err, erl
1010 resume next
