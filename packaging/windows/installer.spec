# -*- mode: python -*-
a = Analysis(['pcbasic'],
             pathex=['C:\\Documents and Settings\\rob\\My Documents\\Projects\\pc-basic_distributions\\pc-basic'],
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
          console=False , 
	  icon='C:\\Documents and Settings\\rob\\My Documents\\Projects\\pc-basic_distributions\\pc-basic\\resources\\pcbasic.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               Tree('font', prefix='font'),
               Tree('encoding', prefix='encoding'),
               Tree('info', prefix='info'),
               strip=None,
               upx=True,
               name='pcbasic')

