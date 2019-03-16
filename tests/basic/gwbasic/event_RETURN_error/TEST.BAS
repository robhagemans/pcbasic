1 ' this tests an old bug where event routine did not return to the right location
2 ' this would trigger an error at COLOR -1
3 open "errors.txt" for output as 1
4 on error goto 2000
5 CLS
10 ON TIMER(1) GOSUB 1000
20 TIMER ON
30 WHILE 1:LOCATE 10,1
40 C=-1:IF 1 THEN C=7:COLOR C: PRINT I; ELSE PRINT "NO1";
50 C=-1:IF 0 THEN PRINT "NO2" ELSE C=7:COLOR C : PRINT I;
100 I=I+1: WEND
999 END
1000 PRINT "HIT";
1005 if I > 100 then end
1010 RETURN
2000 print#1, err, erl
2020 resume next

