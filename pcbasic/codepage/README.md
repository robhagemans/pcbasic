PC-BASIC codepages
------------------

Numbered code pages refer to the OEM code pages as defined by Microsoft.
Where there is a numbering conflict or unclarity, names are used instead of
numbers. Numbered code pages agree with Microsoft sources in the ranges 80-FF,
where those sources are available.
Code point 00 is always treated as NUL and shown as empty space.
The printable ASCII points 20-7E always map to the corresponding ASCII characters.
If the code page reassigns any of the printable ASCII, the reassigned glyph is
used but the character continues to be treated as its ASCII original.
Most code pages use the Special Graphic Characters range at 01-1F and 7F; the
mapping is at http://www.unicode.org/Public/MAPPINGS/VENDORS/MISC/IBMGRAPH.TXT  

See the PC-BASIC documentation for a list of supported codepages and
their names, which agree with the file names in this directory.  

Additional notes on some codepages:  

| Codepage   | Notes  
|------------|----------------------------------------------------------------  
|        874 | MS-DOS Thai. Note that combining diacritics are not handled.  
|        932 | MS-DOS Japanese. Superset of Shift-JIS, except 7e is TILDE not OVERLINE.  
|        936 | Windows Simplified Chinese GBK. Superset of GB2312/EUC-CN.  
|        949 | MS-DOS Korean. Superset of EUC-KR.  
|        950 | MS-DOS Traditional Chinese. Variant of Big-5.  
|       1258 | Windows Vietnamese. Note that combining diacritics are not handled.  
|    Mazovia | Mazovia encoding (Polish). Variously known as code page 667, 991, 790.  
|  Kamenicky | Kamenický encoding (Czech/Slovak). Also known as 895, but conflicting.  
|        mik | MIK encoding (Bulgarian). Also known as FreeDOS 3021.  
|     viscii | VISCII encoding (Vietnamese). Also known as FreeDOS 30006.  
| armscii-8a | ArmSCII-8A encoding (Armenian). Also known as FreeDOS 899.  
|  big5-2003 | Big 5 (traditional Chinese). Taiwanese 2003 standard.  
| big5-hkscs | Big 5 (traditional Chinese). Hong Kong 2008 standard.  
