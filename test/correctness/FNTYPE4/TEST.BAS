10 REM PC-BASIC test
20 REM DEF FN name retrieval
30 defstr s, t
40 def fns(t) = string$(t+1, "x")
60 open "output.txt" for output as 1
70 on error goto 200
80 print#1, fns(1)
82 print#1, fns("1")
85 print#1, fns$(1)
87 print#1, fns$("1")
120 defint t
180 print#1, fns(1)
182 print#1, fns("1")
185 print#1, fns$(1)
187 print#1, fns$("1")
199 end
200 print#1, "error", err, erl
210 resume next
