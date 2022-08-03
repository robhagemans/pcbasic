10 ' test illegal array dimensions 
20 open "errors.txt" for output as 1
30 on error goto 100
40 dim a(-1) ' illegal function call
50 option base 1
60 dim a(0) ' subscript out of range
99 close: end
100 print#1, using "error ### at ###"; err; erl
110 resume next

