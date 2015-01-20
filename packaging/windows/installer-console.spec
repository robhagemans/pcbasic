basedir='..\\..'
# -*- mode: python -*-
a = Analysis([basedir+'\\pcbasic'],
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
          console=True, 
    	  icon='pcbasic.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               Tree(basedir+'\\font', prefix='font'),
               Tree(basedir+'\\encoding', prefix='encoding'),
               Tree(basedir+'\\info', prefix='info'),
               Tree(basedir+'\\config', prefix='config'),
               strip=None,
               upx=True,
               name='pcbasic')

