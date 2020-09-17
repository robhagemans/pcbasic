10 rem PC-BASIC test 
20 rem Long filenames with dots
22 on error goto 500
25 open "output.txt" for output as 1
30 chain merge "LongFileName", 40
40 gosub 1000:print#1, a$
50 chain merge "LongFileName.BAS", 60
60 gosub 1000:print#1, a$
110 chain merge "Long.FileName", 120
120 gosub 1000:print#1, a$
130 chain merge "LongFileName2", 140
140 gosub 1000:print#1, a$
150 chain merge "LongFileName2.bas", 160
160 gosub 1000:print#1, a$
170 chain merge "LongFileName2.", 180
180 gosub 1000:print#1, a$
210 chain merge "Long.FileName.2", 220
220 gosub 1000:print#1, a$
400 print#1,"<end>":close:end
500 print#1, err, erl
510 resume next
