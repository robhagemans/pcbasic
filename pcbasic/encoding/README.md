PC-BASIC codepages
------------------

Numbered code pages refer to the OEM code pages as defined by Microsoft.
Where there is a numbering conflict or unclarity, names are used instead of
numbers. Numbered code pages agree with Microsoft sources in the ranges 80-FF,
where those sources are available.
Code points 00, 20-7E must map to the corresponding ASCII values.
Most code pages use the Special Graphic Characters range at 01-1F and 7F; the
mapping is at http://www.unicode.org/Public/MAPPINGS/VENDORS/MISC/IBMGRAPH.TXT  

See the PC-BASIC documentation for a list of supported codepages and
their names, which agree with the file names in this directory.  

Additional notes on some codepages:  

| Codepage   | Notes  
|------------|----------------------------------------------------------------  
|        864 | MS-DOS Arabic. Note that 0x25 is mapped to %, not ARABIC PERCENT SIGN.  
|        866 | MS-DOS Cyrillic Russian. Also known as Alternativny Variant.  
|        874 | MS-DOS Thai. Note that combining diacritics are not handled.  
|        932 | MS-DOS Japanese. Superset of Shift-JIS. 5c, 7e are mapped to \, ~, not YEN, OVERLINE.  
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
