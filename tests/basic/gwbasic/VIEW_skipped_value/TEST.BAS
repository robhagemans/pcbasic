10 ' test VIEW and VIEW SCREEN with skipped values give no error
15 open "output.txt" for output as 1
16 on error goto 100
20 screen 2
30 view (10,10)-(100,100),,1
50 view screen (10,10)-(100,100),,1
90 end
100 print#1, err, erl
110 resume next

