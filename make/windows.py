"""
PC-BASIC - packaging.windows
Windows packaging

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import distutils
import msilib

import cx_Freeze
from cx_Freeze import Executable

from .common import NAME, VERSION, COPYRIGHT
from .common import make_clean, build_icon, make_docs, prune, remove, mkdir
from .freeze import SHORT_VERSION, COMMANDS, INCLUDE_FILES, EXCLUDE_FILES, PLATFORM_TAG
from .freeze import build_manifest

UPGRADE_CODE = '{714d23a9-aa94-4b17-87a5-90e72d0c5b8f}'
PRODUCT_CODE = msilib.gen_uuid()


def package(**setup_options):
    """Build a Windows .MSI package."""

    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            build_icon()
            make_docs()
            # only include 32-bit DLLs
            build_manifest(INCLUDE_FILES + ('pcbasic/lib/win32_x86/*',), EXCLUDE_FILES)
            cx_Freeze.build_exe.run(self)
            build_dir = 'build/exe.{}/'.format(PLATFORM_TAG)
            # build_exe just includes everything inside the directory
            # so remove some stuff we don't need
            for root, _, files in os.walk(build_dir + 'lib'):
                testing = set(root.split(os.sep)) & set(('test', 'tests', 'testing', 'examples'))
                for fname in files:
                    name = os.path.join(root, fname)
                    if (
                            # remove superfluous copies of python27.dll in lib/
                            # as there is a copy in the package root already
                            fname.lower() == 'python37.dll' or fname.lower() == 'msvcr90.dll'
                            # remove tests and examples
                            or testing
                            # we're only producing packages for win32_x86
                            or 'win32_x64' in name or name.endswith('.dylib')
                        ):
                        remove(name)
            # remove lib dir altogether to avoid it getting copied into the msi
            # as everything in there is copied once already
            prune('build/lib')
            # remove c++ runtime etc
            # these were on python 2.7
            remove(build_dir + 'msvcm90.dll')
            remove(build_dir + 'msvcp90.dll')
            # chunky libs on python3.7 that I don't think we use
            remove(build_dir + 'lib/libcrypto-1_1.dll')
            remove(build_dir + 'lib/libssl-1_1.dll')
            # unneeded sdl2 bits
            remove(build_dir + 'lib/sdl2dll/dll/SDL2_image.dll')
            remove(build_dir + 'lib/sdl2dll/dll/SDL2_mixer.dll')
            remove(build_dir + 'lib/sdl2dll/dll/SDL2_ttf.dll')
            remove(build_dir + 'lib/sdl2dll/dll/libwebp-7.dll')
            remove(build_dir + 'lib/sdl2dll/dll/libtiff-5.dll')
            remove(build_dir + 'lib/sdl2dll/dll/libopus-0.dll')
            remove(build_dir + 'lib/sdl2dll/dll/libmodplug-1.dll')
            # remove modules that can be left out
            for module in (
                    'distutils', 'setuptools', 'pydoc_data', 'lib2to3', 'pip', 'unittest',
                    'wheel', 'lxml',
                    'multiprocessing', 'asyncio'
                ):
                prune(build_dir + 'lib/%s' % module)


    class BdistMsiCommand(cx_Freeze.bdist_msi):
        """Custom bdist_msi command."""

        def run(self):
            """Run build_msi command."""
            name = '{}-{}'.format(NAME, VERSION)
            remove('dist/{}.msi'.format(name))
            cx_Freeze.bdist_msi.run(self)
            # close the database file so we can rename the file
            del self.db
            os.rename('dist/{}-win32.msi'.format(name), 'dist/{}.msi'.format(name))
            make_clean()

        def add_config(self):
            """Override cx_Freeze add_config."""
            # mostly copy-paste from cxfreeze source, wich some changes
            if self.directories:
                msilib.add_data(self.db, "Directory", self.directories)
            msilib.add_data(
                self.db, 'CustomAction',
                [("A_SET_TARGET_DIR", 256 + 51, "TARGETDIR", self.initial_target_dir)]
            )
            if self.add_to_path:
                msilib.add_data(
                    self.db, 'Environment', [("E_PATH", "=-*Path", r"[~];[TARGETDIR]", "TARGETDIR")]
                )
            msilib.add_data(self.db, 'InstallUISequence', [
                ("PrepareDlg", None, 140),
                # this is new
                # sould probably be conditional on "not already installed" or smth
                ("WhichUsersDlg", "not Installed", 400),
                ("A_SET_TARGET_DIR", 'TARGETDIR=""', 401),
                ("SelectDirectoryDlg", "not Installed", 1230),
                ("MaintenanceTypeDlg", "Installed and not Resume and not Preselected", 1250),
                ("ProgressDlg", None, 1280),
            ])
            msilib.add_data(self.db, 'InstallExecuteSequence', [
                ("A_SET_TARGET_DIR", 'TARGETDIR=""', 401),
                ('WriteEnvironmentStrings', 'MSIINSTALLPERUSER=""', 5200),
            ])
            for index, executable in enumerate(self.distribution.executables):
                if executable.shortcut_name is not None and executable.shortcut_dir is not None:
                    base_name = os.path.basename(executable.target_name)
                    msilib.add_data(
                        self.db, "Shortcut", [(
                            "S_APP_%s" % index, executable.shortcut_dir, executable.shortcut_name,
                            "TARGETDIR", "[TARGETDIR]%s" % base_name,
                            None, None, None, None, None, None, None
                        )]
                    )
            for table_name, data in self.data.items():
                col = self._binary_columns.get(table_name)
                if col is not None:
                    data = [
                        (*row[:col], msilib.Binary(row[col].name), *row[col + 1 :])
                        for row in data
                    ]
                msilib.add_data(self.db, table_name, data)

        def add_properties(self):
            """Override cx_Freeze add_properties."""
            # mostly copy-paste from cxfreeze
            metadata = self.distribution.metadata
            props = [
                ('DistVersion', metadata.get_version()),
                ('DefaultUIFont', 'DlgFont8'),
                ('ErrorDialog', 'ErrorDlg'),
                ('Progress1', 'Install'),
                ('Progress2', 'installs'),
                ('MaintenanceForm_Action', 'Repair'),
                ('ALLUSERS', '2'),
                ('MSIINSTALLPERUSER', '1'),
            ]
            email = metadata.author_email or metadata.maintainer_email
            if email:
                props.append(("ARPCONTACT", email))
            if metadata.url:
                props.append(("ARPURLINFOABOUT", metadata.url))
            if self.upgrade_code is not None:
                props.append(("UpgradeCode", self.upgrade_code))
            msilib.add_data(self.db, 'Property', props)

        def _add_whichusers_dialog(self):
            """Per-user or per-machine install dialog."""
            # based on dialog from cpython 2.7 source code
            # https://svn.python.org/projects/python/trunk/Tools/msi/msi.py
            whichusers = cx_Freeze.command.bdist_msi.PyDialog(
                self.db, "WhichUsersDlg", self.x, self.y, self.width, self.height,
                self.modal, self.title, "AdminInstall", "Next", "Cancel"
            )
            whichusers.title(
                "Select for which users to install [ProductName]."
            )
            # A radio group with two options: allusers, justme
            radio = whichusers.radiogroup(
                "AdminInstall", 135, 60, 235, 80, 3, "WhichUsers", "", "Next"
            )
            radio.condition("Disable", "VersionNT=600") # Not available on Vista and Windows 2008
            radio.add("ALL", 0, 5, 150, 20, "Install for all users")
            radio.add("JUSTME", 0, 25, 235, 20, "Install just for me")

            whichusers.backbutton("Back", None, active=0)

            button = whichusers.nextbutton("Next >", "Cancel")
            # SetProperty events
            # https://docs.microsoft.com/en-us/windows/desktop/Msi/setproperty-controlevent
            button.event("[MSIINSTALLPERUSER]", "{}", 'WhichUsers="ALL"', 1)
            button.event("[MSIINSTALLPERUSER]", "1", 'WhichUsers="JUSTME"', 1)
            # set the target dir to the default location for per-user/per-machine installs
            button.event(
                "[TARGETDIR]",
                "[ProgramFilesFolder]\\%s %s" % (NAME, SHORT_VERSION),
                'WhichUsers="JUSTME"', 1
            )
            button.event("EndDialog", "Return", 3)

            button = whichusers.cancelbutton("Cancel", "AdminInstall")
            button.event("SpawnDialog", "CancelDlg")

        def add_ui(self):
            self._add_whichusers_dialog()
            cx_Freeze.bdist_msi.add_ui(self)


    # remove the WriteEnvironmentStrings action from the default list
    # since cx_Freeze picks up the default list and puts it into the MSI
    # but we can't have environment changes for per-user installs (?)
    sequence = msilib.sequence.InstallExecuteSequence
    for index, info in enumerate(sequence):
        if info[0] == u'WriteEnvironmentStrings':
            break
    del sequence[index]

    # setup commands
    setup_options['cmdclass'] = dict(
        build_exe=BuildExeCommand,
        bdist_msi=BdistMsiCommand,
        **COMMANDS
    )

    numversion = '.'.join(v for v in VERSION.split('.') if v.isdigit())

    # these must be bytes for cx_Freeze bdist_msi
    setup_options['name'] = NAME
    setup_options['author'] = AUTHOR
    setup_options['version'] = numversion

    # compile separately, as they end up in the wrong place anyway
    setup_options['ext_modules'] = []

    # gui launcher
    setup_options['entry_points']['gui_scripts'] = ['pcbasicw=pcbasic:main']

    directory_table = [
        (
            'StartMenuFolder',
            'TARGETDIR',
            '.',
        ),
        (
            'MyProgramMenu',
            'StartMenuFolder',
            'PCBASI~1|PC-BASIC {}'.format(SHORT_VERSION),
        ),
    ]
    # https://stackoverflow.com/questions/15734703/use-cx-freeze-to-create-an-msi-that-adds-a-shortcut-to-the-desktop#15736406
    shortcut_table = [
        (
            'ProgramShortcut',        # Shortcut
            'MyProgramMenu',          # Directory_
            'PC-BASIC %s' % VERSION,  # Name
            'TARGETDIR',              # Component_
            '[TARGETDIR]pcbasicw.exe',# Target
            None,                     # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            # PersonalFolder is My Documents, use as Start In folder
            'PersonalFolder'          # WkDir
        ),
        (
            'DocShortcut',            # Shortcut
            'MyProgramMenu',          # Directory_
            'Documentation',          # Name
            'TARGETDIR',              # Component_
            '[TARGETDIR]PC-BASIC_documentation.html', # Target
            None,                     # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            'TARGETDIR'               # WkDir
        ),
        (
            'SettingsShortcut',            # Shortcut
            'MyProgramMenu',          # Directory_
            'Settings',               # Name
            'TARGETDIR',              # Component_
            '[AppDataFolder]pcbasic-{}\\PCBASIC.INI'.format(SHORT_VERSION), # Target
            None,                     # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            'TARGETDIR'               # WkDir
        ),
        (
            'UninstallShortcut',      # Shortcut
            'MyProgramMenu',          # Directory_
            'Uninstall',              # Name
            'TARGETDIR',              # Component_
            '[SystemFolder]msiexec.exe', # Target
            '/x %s' % PRODUCT_CODE,           # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            # PersonalFolder is My Documents, use as Start In folder
            'TARGETDIR'               # WkDir
        ),
    ]
    msi_data = {
        'Directory': directory_table,
        'Shortcut': shortcut_table,
        'Icon': [('PC-BASIC-Icon', msilib.Binary('./resources/pcbasic.ico')),],
        'Property': [('ARPPRODUCTICON', 'PC-BASIC-Icon'),],
    }

    # cx_Freeze options
    setup_options['options'] = {
        'build_exe': {
            'packages': ['pkg_resources._vendor'],
            'excludes': [
                'Tkinter', '_tkinter', 'PIL', 'PyQt4', 'scipy', 'pygame',
                'pywin', 'win32com', 'test',
            ],
            'include_files': ['doc/PC-BASIC_documentation.html'],
            'include_msvcr': True,
            #'optimize': 2,
        },
        'bdist_msi': {
            'data': msi_data,
            # add console entry points to PATH
            'add_to_path': True,
            # enforce removal of old versions
            'upgrade_code': UPGRADE_CODE,
            'product_code': PRODUCT_CODE,
            'initial_target_dir': 'c:\\Program Files\\%s %s' % (NAME, SHORT_VERSION),
        },
    }

    setup_options['executables'] = [
        Executable(
            'pc-basic', base='Console', targetName='pcbasic.exe', icon='resources/pcbasic.ico',
            copyright=COPYRIGHT),
        Executable(
            'pc-basic', base='Win32GUI', targetName='pcbasicw.exe', icon='resources/pcbasic.ico',
            #shortcutName='PC-BASIC %s' % VERSION, shortcutDir='MyProgramMenu',
            copyright=COPYRIGHT),
    ]

    # call cx_Freeze's setup() with command bdist_msi
    cx_Freeze.setup(script_args=['bdist_msi'], **setup_options)
