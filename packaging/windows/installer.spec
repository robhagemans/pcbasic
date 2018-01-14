basedir='..\\..'
# -*- mode: python -*-
a = Analysis([basedir+'\\run.py'],
             pathex=[basedir],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None,
             excludes=['_tkinter', 'tcl', 'tk', '_ssl', '_bsddb', '_hashlib'])
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='pcbasic.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False,
	  icon='pcbasic.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               a.binaries + [('simpleio.dll', 'c:\\python27\\lib\\site-packages\\parallel\\simpleio.dll', 'BINARY')],
               Tree(basedir+'\\pcbasic\\font', prefix='font'),
               Tree(basedir+'\\pcbasic\\codepage', prefix='codepage'),
               Tree(basedir+'\\pcbasic\\data', prefix='data'),
               Tree(basedir+'\\doc', prefix='doc'),
               strip=None,
               upx=True,
               name='pcbasic')
