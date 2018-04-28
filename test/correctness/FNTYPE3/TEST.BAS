10 REM PC-BASIC test
20 REM DEF FN name retrieval
30 defstr s, t
40 def fns(t) = chr$(len(t))
50 def fnk$(t$) = chr$(len(t$))
60 open "output.txt" for output as 1
70 on error goto 200
80 print#1, fns("1")
90 defint s
100 print#1, fns$("12")
110 print#1, fns("12")
120 defint t
130 print#1, fnk$("12")
140 print#1, fns$("12")
150 print#1, fns$(12)
160 print#1, fnk$(12)
170 print#1, fns(12)
180 print#1, fnk("12")
190 print#1, fnk(12)
199 end
200 print#1, "error", err, erl
210 resume next
