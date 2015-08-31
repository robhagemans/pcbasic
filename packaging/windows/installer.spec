basedir='..\\..'
# -*- mode: python -*-
a = Analysis([basedir+'\\pcbasic.py'],
             pathex=[basedir],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
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
               Tree(basedir+'\\pcbasic\\font', prefix='font'),
               Tree(basedir+'\\pcbasic\\encoding', prefix='encoding'),
               Tree(basedir+'\\pcbasic\\data', prefix='data'),
               Tree(basedir+'\\doc', prefix='doc'),
               strip=None,
               upx=True,
               name='pcbasic')
