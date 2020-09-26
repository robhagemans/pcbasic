10 ' run out of memory in string equation
15 on error goto 60
18 dim a$(1000)
20 for i = 0 to 1000
30 a$(i) = STRING$(100, "a") + STRING$(100, "b")
40 next
50 end
60 open "errors.txt" for output as 1
70 print#1, err, erl, i, a$(i)
80 close: resume 50

