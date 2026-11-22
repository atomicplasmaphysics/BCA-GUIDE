from typing import Dict, Optional, Tuple


from PyQt6.QtCore import Qt, QByteArray, QRect, QRectF, QSize
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QIconEngine, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer


from Utility.Styles import Styles


# Icons are taken from Lucide (https://lucide.dev), ISC License
# Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT).
# All other copyright (c) for Lucide are held by Lucide Contributors 2022.


def isDarkTheme() -> bool:
    """Returns if the current theme is dark"""

    return QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


class ThemeIconEngine(QIconEngine):
    """
    Icon engine that renders a svg icon in the color of the current theme (also after theme changes)

    :param name: name of icon in icons
    """

    # lucide icons, name: (accent color or None for text color, svg content in a 24x24 viewbox)
    icons: Dict[str, Tuple[Optional[str], str]] = {
        # file-plus
        'new': (None, '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /> <path d="M14 2v4a2 2 0 0 0 2 2h4" /> <path d="M9 15h6" /> <path d="M12 18v-6" />'),
        # folder-open
        'open': (None, '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2" />'),
        # file-input
        'convert': (None, '<path d="M4 22h14a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v4" /> <path d="M14 2v4a2 2 0 0 0 2 2h4" /> <path d="M2 15h10" /> <path d="m9 18 3-3-3-3" />'),
        # save
        'save': (None, '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /> <path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7" /> <path d="M7 3v4a1 1 0 0 0 1 1h7" />'),
        # save-all
        'save_as': (None, '<path d="M10 2v3a1 1 0 0 0 1 1h5" /> <path d="M18 18v-6a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6" /> <path d="M18 22H4a2 2 0 0 1-2-2V6" /> <path d="M8 18a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9.172a2 2 0 0 1 1.414.586l2.828 2.828A2 2 0 0 1 22 6.828V16a2 2 0 0 1-2.01 2z" />'),
        # settings
        'preferences': (None, '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" /> <circle cx="12" cy="12" r="3" />'),
        # refresh-cw
        'refresh': (None, '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /> <path d="M21 3v5h-5" /> <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /> <path d="M8 16H3v5" />'),
        # rotate-ccw
        'reset': (None, '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /> <path d="M3 3v5h5" />'),
        # circle-x
        'close': (None, '<circle cx="12" cy="12" r="10" /> <path d="m15 9-6 6" /> <path d="m9 9 6 6" />'),
        # circle-plus
        'add': (None, '<circle cx="12" cy="12" r="10" /> <path d="M8 12h8" /> <path d="M12 8v8" />'),
        # chevron-up
        'up': (None, '<path d="m18 15-6-6-6 6" />'),
        # chevron-down
        'down': (None, '<path d="m6 9 6 6 6-6" />'),
        # folder-search
        'open_workdir': (None, '<path d="M10.7 20H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v4.1" /> <path d="m21 21-1.9-1.9" /> <circle cx="17" cy="17" r="3" />'),
        # search
        'search': (None, '<circle cx="11" cy="11" r="8" /> <path d="m21 21-4.3-4.3" />'),
        # file-text
        'file': (None, '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /> <path d="M14 2v4a2 2 0 0 0 2 2h4" /> <path d="M10 9H8" /> <path d="M16 13H8" /> <path d="M16 17H8" />'),
        # external-link
        'open_external': (None, '<path d="M15 3h6v6" /> <path d="M10 14 21 3" /> <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />'),
        # spell-check
        'error_check': (None, '<path d="m6 16 6-12 6 12" /> <path d="M8 12h8" /> <path d="m16 20 2 2 4-4" />'),
        # book-open
        'book': ('blue', '<path d="M12 7v14" /> <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />'),
        # circle-help
        'help': ('blue', '<circle cx="12" cy="12" r="10" /> <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /> <path d="M12 17h.01" />'),
        # circle-play
        'play': ('green', '<circle cx="12" cy="12" r="10" /> <polygon points="10 8 16 12 10 16 10 8" />'),
        # sliders-horizontal
        'scan': (None, '<line x1="21" x2="14" y1="4" y2="4" /> <line x1="10" x2="3" y1="4" y2="4" /> <line x1="21" x2="12" y1="12" y2="12" /> <line x1="8" x2="3" y1="12" y2="12" /> <line x1="21" x2="16" y1="20" y2="20" /> <line x1="12" x2="3" y1="20" y2="20" /> <line x1="14" x2="14" y1="2" y2="6" /> <line x1="8" x2="8" y1="10" y2="14" /> <line x1="16" x2="16" y1="18" y2="22" />'),
        # arrow-right-left
        'compare': (None, '<path d="m16 3 4 4-4 4" /> <path d="M20 7H4" /> <path d="m8 21-4-4 4-4" /> <path d="M4 17h16" />'),
        # chart-line
        'chart': (None, '<path d="M3 3v16a2 2 0 0 0 2 2h16" /> <path d="m19 9-5 5-4-4-3 3" />'),
        # clock
        'clock': (None, '<circle cx="12" cy="12" r="10" /> <polyline points="12 6 12 12 16 14" />'),
        # circle-pause
        'pause': (None, '<circle cx="12" cy="12" r="10" /> <line x1="10" x2="10" y1="15" y2="9" /> <line x1="14" x2="14" y1="15" y2="9" />'),
        # square-terminal
        'play_detached': ('green', '<path d="m7 11 2-2-2-2" /> <path d="M11 13h4" /> <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />'),
        # ban
        'abort': ('red', '<circle cx="12" cy="12" r="10" /> <path d="m4.9 4.9 14.2 14.2" />'),
        # check
        'okay': ('green', '<path d="M20 6 9 17l-5-5" />'),
        # triangle-alert
        'warning': ('orange', '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" /> <path d="M12 9v4" /> <path d="M12 17h.01" />'),
        # circle-x
        'error': ('red', '<circle cx="12" cy="12" r="10" /> <path d="m15 9-6 6" /> <path d="m9 9 6 6" />'),
    }

    svg_template = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{content}</svg>'

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.accent, self.content = self.icons[name]

    def color(self, mode: QIcon.Mode) -> QColor:
        """
        Returns color of icon

        :param mode: mode of icon
        """

        palette = QGuiApplication.palette()
        if mode == QIcon.Mode.Disabled:
            return palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
        if self.accent is not None:
            light, dark = Styles.accent_colors[self.accent]
            return QColor(dark if isDarkTheme() else light)
        return palette.color(QPalette.ColorRole.WindowText)

    def paint(self, painter: Optional[QPainter], rect: QRect, mode: QIcon.Mode, state: QIcon.State):
        """
        Paints icon

        :param painter: painter to paint with
        :param rect: rectangle to paint into
        :param mode: mode of icon
        :param state: state of icon
        """

        if painter is None:
            return

        svg = self.svg_template.format(color=self.color(mode).name(), content=self.content)
        renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
        side = min(rect.width(), rect.height())
        renderer.render(painter, QRectF(
            rect.x() + (rect.width() - side) / 2,
            rect.y() + (rect.height() - side) / 2,
            side,
            side
        ))

    def scaledPixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float) -> QPixmap:
        """
        Returns pixmap of icon

        :param size: size of pixmap
        :param mode: mode of icon
        :param state: state of icon
        :param scale: device pixel ratio
        """

        pixmap = QPixmap(size * scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint(painter, QRect(0, 0, pixmap.width(), pixmap.height()), mode, state)
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        """
        Returns pixmap of icon

        :param size: size of pixmap
        :param mode: mode of icon
        :param state: state of icon
        """

        return self.scaledPixmap(size, mode, state, 1.0)

    def clone(self) -> 'ThemeIconEngine':
        """Returns a copy of the engine"""

        return ThemeIconEngine(self.name)


def getIcon(name: str) -> QIcon:
    """
    Returns a theme aware icon

    :param name: name of icon, see ThemeIconEngine.icons
    """

    return QIcon(ThemeIconEngine(name))


def getPixmap(name: str, size: int) -> QPixmap:
    """
    Returns pixmap of icon in the current theme

    :param name: name of icon, see ThemeIconEngine.icons
    :param size: size of pixmap in pixels
    """

    return getIcon(name).pixmap(size)
