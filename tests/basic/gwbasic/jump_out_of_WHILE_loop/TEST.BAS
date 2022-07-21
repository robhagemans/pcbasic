5 tron
10 ' test jumping out of WHILE loop 
20 open "output.txt" for output as 1
25 on error goto 1000
29 ' jump out of loop onto extra WEND
30 while a<3
40 a=a+1
50 print#1,a
60 goto 80
70 wend
80 wend
90 print#1,  "out 0"
100 ' plain jump out of loop
120 a=0
130 while a<3
140 a=a+1
150 print#1,a
160 goto 180
170 wend
180 print#1, "out 1"
200 ' jump out of inner loop
210 a=0:b=0
220 while b<3
230 while a<3
240 a=a+1:b=b+1
250 print#1,a, b
260 goto 280
265 'if a+b > 10 then 290
270 wend
280 wend
290 print#1, "out 3"
300 close
310 end
1000 print#1, "error: "; err; " in "; erl
1010 resume next

