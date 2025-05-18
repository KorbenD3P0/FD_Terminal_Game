# -*- mode: python ; coding: utf-8 -*-
import os
from kivy_deps import sdl2, glew
block_cipher = None

a = Analysis(['main.py'],
             pathex=[os.getcwd()],  # Use getcwd() instead of __file__
             binaries=[],
             datas=[],
             hiddenimports=['fd_terminal.game_data', 'fd_terminal.hazard_engine', 'fd_terminal.ui', 'fd_terminal.hazard_patch', 'kivy', 'kivy.core.text', 'kivy.core.window', 'json'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

# Add ALL asset files with proper directory structure
for root, dirs, files in os.walk('fd_terminal'):
    for file in files:
        source_path = os.path.join(root, file)
        a.datas.append((source_path, source_path, 'DATA'))

# Add font files correctly
font_files = [
   ('assets\\fonts\\RobotoMono-Regular.ttf', 'assets\\fonts\\RobotoMono-Regular.ttf', 'DATA'),
   ('assets\\fonts\\RobotoMono-Bold.ttf', 'assets\\fonts\\RobotoMono-Bold.ttf', 'DATA'),
   ('fd_terminal\\assets\\fonts\\RobotoMono-Regular.ttf', 'fd_terminal\\assets\\fonts\\RobotoMono-Regular.ttf', 'DATA'),
   ('fd_terminal\\assets\\fonts\\RobotoMono-Bold.ttf', 'fd_terminal\\assets\\fonts\\RobotoMono-Bold.ttf', 'DATA')
]
a.datas.extend(font_files)

# Add critical data directories
a.datas += [('data\\placeholder', 'data\\placeholder', 'DATA')]
a.datas += [('assets\\placeholder', 'assets\\placeholder', 'DATA')]
a.datas += [('fd_terminal\\data\\placeholder', 'fd_terminal\\data\\placeholder', 'DATA')]
a.datas += [('fd_terminal\\assets\\placeholder', 'fd_terminal\\assets\\placeholder', 'DATA')]

# Explicitly include key Python modules
a.datas += [('fd_terminal\\game_data.py', 'fd_terminal\\game_data.py', 'DATA')]
a.datas += [('fd_terminal\\hazard_patch.py', 'fd_terminal\\hazard_patch.py', 'DATA')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins)],
          name='FD_Terminal_Game',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True)