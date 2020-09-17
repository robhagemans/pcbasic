1 ' test box-protection algorithm in codepage 936
2 ' by writing a mix of characters and box-drawing to a utf-8 file
10 X=1:Y=1:L=16:N=4
20 open "output.txt" for output as 1
90 M$(1)="  1.  选项一    ":M$(2)="  2.  选项三    "
100 M$(3)="  3.  选项三    ":M$(4)="  4.  选项四    "
140 PRINT#1, CHR$(218);STRING$(L,CHR$(196));CHR$(191)
150 FOR J=1 TO N
160 PRINT#1, CHR$(179);M$(J);CHR$(179):NEXT J
170 PRINT#1, CHR$(192);STRING$(L,CHR$(196));CHR$(217)
180 close#1
