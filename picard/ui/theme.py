# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2019-2022, 2024-2025 Philipp Wolfer
# Copyright (C) 2020-2021 Gabriel Ferreira
# Copyright (C) 2021-2024 Laurent Monin
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.


from enum import Enum

from PyQt6 import (
    QtCore,
    QtGui,
    QtWidgets,
)

from picard import log
from picard.config import get_config
from picard.const.sys import (
    IS_HAIKU,
    IS_MACOS,
    IS_WIN,
)

from picard.ui.theme_detect import get_linux_dark_mode_strategies


# DRY: Common dark background color
DARK_BG_COLOR = QtGui.QColor(51, 51, 51)

# Centralized dark mode palette for Windows and Linux
DARK_PALETTE_COLORS = {
    QtGui.QPalette.ColorRole.Window: DARK_BG_COLOR,
    QtGui.QPalette.ColorRole.WindowText: QtCore.Qt.GlobalColor.white,
    QtGui.QPalette.ColorRole.Base: QtGui.QColor(31, 31, 31),
    QtGui.QPalette.ColorRole.AlternateBase: DARK_BG_COLOR,
    QtGui.QPalette.ColorRole.ToolTipBase: DARK_BG_COLOR,
    QtGui.QPalette.ColorRole.ToolTipText: QtCore.Qt.GlobalColor.white,
    QtGui.QPalette.ColorRole.Text: QtCore.Qt.GlobalColor.white,
    QtGui.QPalette.ColorRole.Button: DARK_BG_COLOR,
    QtGui.QPalette.ColorRole.ButtonText: QtCore.Qt.GlobalColor.white,
    QtGui.QPalette.ColorRole.BrightText: QtCore.Qt.GlobalColor.red,
    (QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text): QtCore.Qt.GlobalColor.darkGray,
    (QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Light): QtGui.QColor(0, 0, 0, 0),
    (QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText): QtCore.Qt.GlobalColor.darkGray,
    (QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Base): QtGui.QColor(60, 60, 60),
    (QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Highlight): DARK_BG_COLOR,
    (QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.HighlightedText): QtCore.Qt.GlobalColor.white,
}


OS_SUPPORTS_THEMES = True
AppKit = None
winreg = None
if IS_MACOS:
    try:
        import AppKit
    except ImportError:
        AppKit = None

    OS_SUPPORTS_THEMES = bool(AppKit) and hasattr(AppKit.NSAppearance, '_darkAquaAppearance')

elif IS_HAIKU:
    OS_SUPPORTS_THEMES = False
elif IS_WIN:
    import winreg


# Those are values stored in config file:
class UiTheme(Enum):
    DEFAULT = 'default'
    DARK = 'dark'
    LIGHT = 'light'
    SYSTEM = 'system'

    def __str__(self):
        return self.value

    @classmethod
    def _missing_(cls, value):
        return cls.DEFAULT


AVAILABLE_UI_THEMES = [UiTheme.DEFAULT]
if IS_WIN or IS_MACOS:
    AVAILABLE_UI_THEMES.extend([UiTheme.LIGHT, UiTheme.DARK])
elif not IS_HAIKU:
    AVAILABLE_UI_THEMES.extend([UiTheme.SYSTEM])


class MacOverrideStyle(QtWidgets.QProxyStyle):
    """Override the default style to fix some platform specific issues"""

    def styleHint(self, hint, option, widget, returnData):
        # This is disabled on macOS, but prevents collapsing tree view items easily with
        # left arrow key. Enable this consistently on all platforms.
        # See https://tickets.metabrainz.org/browse/PICARD-2417
        # and https://bugreports.qt.io/browse/QTBUG-100305
        if hint == QtWidgets.QStyle.StyleHint.SH_ItemView_ArrowKeysNavigateIntoChildren:
            return True
        return super().styleHint(hint, option, widget, returnData)


class BaseTheme:
    def __init__(self):
        self._dark_theme = False
        self._loaded_config_theme = UiTheme.DEFAULT
        # Registry of dark mode detection strategies for Linux DEs
        self._dark_mode_strategies = get_linux_dark_mode_strategies()

    def _detect_linux_dark_mode(self) -> bool:
        # Iterate through all registered strategies
        for strategy in self._dark_mode_strategies:
            if strategy():
                return True
        log.debug("No Linux system dark mode detected, defaulting to light mode.")
        return False

    def setup(self, app):
        config = get_config()
        ui_theme = config.setting['ui_theme']
        self._loaded_config_theme = UiTheme(config.setting['ui_theme'])

        # Use the new fusion style from PyQt6 for a modern and consistent look
        # across all OSes.
        if not IS_MACOS and not IS_HAIKU and self._loaded_config_theme != UiTheme.SYSTEM:
            app.setStyle('Fusion')
        elif IS_MACOS:
            app.setStyle(MacOverrideStyle(app.style()))

        app.setStyleSheet(
            'QGroupBox::title { /* PICARD-1206, Qt bug workaround */ }',
        )

        palette = QtGui.QPalette(app.palette())
        base_color = palette.color(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Base)
        self._dark_theme = base_color.lightness() < 128
        self._accent_color = None
        if self._dark_theme:
            self._accent_color = palette.color(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Highlight)

        # Linux-specific: If SYSTEM theme, try to detect system dark mode
        # Do not apply override if already dark theme
        is_dark_theme = self.is_dark_theme
        if (
            not self._dark_theme
            and not IS_WIN
            and not IS_MACOS
            and not IS_HAIKU
            and self._loaded_config_theme == UiTheme.SYSTEM
        ):
            is_dark_theme = self._detect_linux_dark_mode()
            if is_dark_theme:
                # Apply a dark palette centrally defined
                for key, value in DARK_PALETTE_COLORS.items():
                    if isinstance(key, tuple):
                        group, role = key
                        palette.setColor(group, role, value)
                    else:
                        palette.setColor(key, value)
                self._dark_theme = True
                self._accent_color = palette.color(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Highlight)
            else:
                self._dark_theme = False
                self._accent_color = None

        accent_color = self.accent_color
        if accent_color:
            accent_color_str = accent_color.name(QtGui.QColor.NameFormat.HexArgb)
        else:
            accent_color_str = "None"

        log.debug(
            "Theme: %s (%s) dark=%s accent_color=%s",
            ui_theme,
            self.__class__.__name__,
            is_dark_theme,
            accent_color_str,
        )

        self.update_palette(palette, is_dark_theme, accent_color)
        app.setPalette(palette)

    @property
    def is_dark_theme(self):
        if self._loaded_config_theme == UiTheme.DARK:
            return True
        elif self._loaded_config_theme == UiTheme.LIGHT:
            return False
        else:
            return self._dark_theme

    @property
    def accent_color(self):  # pylint: disable=no-self-use
        return self._accent_color

    # pylint: disable=no-self-use
    def update_palette(self, palette, dark_theme, accent_color):
        if accent_color:
            accent_text_color = (
                QtCore.Qt.GlobalColor.white if accent_color.lightness() < 160 else QtCore.Qt.GlobalColor.black
            )
            palette.setColor(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Highlight, accent_color)
            palette.setColor(
                QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.HighlightedText, accent_text_color
            )

            link_color = QtGui.QColor()
            link_color.setHsl(accent_color.hue(), accent_color.saturation(), 160, accent_color.alpha())
            palette.setColor(QtGui.QPalette.ColorRole.Link, link_color)


# Move `WindowsTheme` to outside of IS_WIN to enable testing.
class WindowsTheme(BaseTheme):
    """Windows dark mode theme."""

    def setup(self, app):
        app.setStyle('Fusion')
        super().setup(app)

    @property
    def is_dark_theme(self):
        if self._loaded_config_theme != UiTheme.DEFAULT:
            return self._loaded_config_theme == UiTheme.DARK
        dark_theme = False
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                dark_theme = winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except OSError:
            log.warning("Failed reading AppsUseLightTheme from registry")
        return dark_theme

    @property
    def accent_color(self):
        accent_color = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
                accent_color_dword = winreg.QueryValueEx(key, "ColorizationColor")[0]
                accent_color_hex = '#{:06x}'.format(accent_color_dword & 0xFFFFFF)
                accent_color = QtGui.QColor(accent_color_hex)
        except OSError:
            log.warning("Failed reading ColorizationColor from registry")
        return accent_color

    def update_palette(self, palette, dark_theme, accent_color):
        # Adapt to Windows 10 color scheme (dark / light theme and accent color)
        super().update_palette(palette, dark_theme, accent_color)
        if dark_theme:
            for key, value in DARK_PALETTE_COLORS.items():
                if isinstance(key, tuple):
                    group, role = key
                    palette.setColor(group, role, value)
                else:
                    palette.setColor(key, value)


if IS_WIN:
    theme = WindowsTheme()

elif IS_MACOS:
    dark_appearance = False
    if OS_SUPPORTS_THEMES and AppKit:
        # Default procedure to identify the current appearance (theme)
        appearance = AppKit.NSAppearance.currentAppearance()
        try:
            basic_appearance = appearance.bestMatchFromAppearancesWithNames_(
                [
                    AppKit.NSAppearanceNameAqua,
                    AppKit.NSAppearanceNameDarkAqua,
                ]
            )
            dark_appearance = basic_appearance == AppKit.NSAppearanceNameDarkAqua
        except AttributeError:
            pass

    class MacTheme(BaseTheme):
        def setup(self, app):
            super().setup(app)

            if self._loaded_config_theme != UiTheme.DEFAULT:
                dark_theme = self._loaded_config_theme == UiTheme.DARK
            else:
                dark_theme = dark_appearance

            # MacOS uses a NSAppearance object to change the current application appearance
            # We call this even if UiTheme is the default, preventing MacOS from switching on-the-fly
            if OS_SUPPORTS_THEMES and AppKit:
                try:
                    if dark_theme:
                        appearance = AppKit.NSAppearance._darkAquaAppearance()
                    else:
                        appearance = AppKit.NSAppearance._aquaAppearance()
                    AppKit.NSApplication.sharedApplication().setAppearance_(appearance)
                except AttributeError:
                    pass

        @property
        def is_dark_theme(self):
            if not OS_SUPPORTS_THEMES:
                # Fall back to generic dark color palette detection
                return super().is_dark_theme
            elif self._loaded_config_theme == UiTheme.DEFAULT:
                return dark_appearance
            else:
                return self._loaded_config_theme == UiTheme.DARK

        # pylint: disable=no-self-use
        def update_palette(self, palette, dark_theme, accent_color):
            pass  # No palette changes, theme is fully handled by Qt

    theme = MacTheme()

else:
    theme = BaseTheme()


def setup(app):
    theme.setup(app)
