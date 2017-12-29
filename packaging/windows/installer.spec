# -*- mode: python -*-
basedir = '..\\..'
a = Analysis(
        [basedir+'\\run.py'],
        pathex=[basedir],
        hiddenimports=['Queue'],
	excludes=['_tkinter', 'tcl', 'tk', 
		'pygame', 'pyaudio', 
		'_ssl', '_bsddb', '_hashlib'],
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
        a.datas + [
            ('SDL2.dll', basedir+'\\pcbasic\\interface\\SDL2.dll', ''),
            ('SDL2_gfx.dll', basedir+'\\pcbasic\\interface\\SDL2_gfx.dll', ''),
            ],
        Tree(basedir+'\\pcbasic\\basic\\font', prefix='pcbasic/basic/font'),
        Tree(basedir+'\\pcbasic\\basic\\codepage', prefix='pcbasic/basic/codepage'),
        Tree(basedir+'\\pcbasic\\basic\\programs', prefix='pcbasic/basic/programs'),
        Tree(basedir+'\\doc', prefix='doc'),
        strip=None,
        upx=True,
        name='pcbasic')
