10 ' test Greek codepage 
20 open "output.txt" for output as 1
30 open "你好世界" for input as 2
40 line input#2, a$
50 print#1, a$
60 close
