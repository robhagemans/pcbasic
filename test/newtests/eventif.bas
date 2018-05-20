5 _trace
10 on timer(1) gosub 1000
20 timer on
30 while 1
40 if 1 then locate 10,10: print i; else print "NO1";
50 if 0 then print "NO2" else locate 12,40: print i;
60 rem play "p4"
100 i=i+1: wend
999 end
1000 locate 20,1:print "HIT":return
