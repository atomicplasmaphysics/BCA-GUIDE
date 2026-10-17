"""
Styles of the BCA-GUIDE: style sheets of widgets (Styles) and the colors of the plots and elements (hypercorporateAF
design): the 12 colors in the order of the palette, further colors are lightened and then darkened versions of them
"""

from typing import Tuple

from PyQt6.QtGui import QColor


PALETTE = [
    '#EA558F', '#F39345', '#FEC927', '#9BC437', '#00AD91', '#00ADC1',
    '#0084C2', '#006699', '#685DA4', '#9A5A9F', '#BD4492', '#CB2649'
]

# first color of plots with only one curve (blue) and colors of layers (lightened yellow, teal, purple, orange, blue)
FIRST_COLOR_INDEX = 6
LAYER_COLORS = [2, 4, 8, 1, 6]


def hexToRgb(color: str) -> Tuple[float, float, float]:
    """Returns (r, g, b) in [0, 1] of a color '#RRGGBB'"""

    color = color.lstrip('#')
    return int(color[0:2], 16) / 255, int(color[2:4], 16) / 255, int(color[4:6], 16) / 255


def paletteRgb(index: int) -> Tuple[float, float, float]:
    """
    Returns the color with an index as (r, g, b) in [0, 1]: the 12 colors of the palette, then lightened (index 12-23),
    darkened (24-35) and again more lightened versions

    :param index: index of the color
    """

    r, g, b = hexToRgb(PALETTE[index % len(PALETTE)])
    variant = (index // len(PALETTE)) % 4
    if variant == 1:
        # lightened: 40 % white
        return r + 0.4 * (1 - r), g + 0.4 * (1 - g), b + 0.4 * (1 - b)
    if variant == 2:
        # darkened: 35 % black
        return 0.65 * r, 0.65 * g, 0.65 * b
    if variant == 3:
        return r + 0.65 * (1 - r), g + 0.65 * (1 - g), b + 0.65 * (1 - b)
    return r, g, b


def paletteHex(index: int) -> str:
    """Returns the color with an index as '#rrggbb'"""

    return '#' + ''.join(f'{round(c * 255):02x}' for c in paletteRgb(index))


def layerHex(index: int) -> str:
    """Returns the (lightened) color of a layer of the target as '#rrggbb'"""

    return paletteHex(len(PALETTE) + LAYER_COLORS[index % len(LAYER_COLORS)])


def paletteQColor(index: int, alpha: int = 255) -> QColor:
    """Returns the color with an index as <QColor>"""

    color = QColor(paletteHex(index))
    color.setAlpha(alpha)
    return color


class Palette(list):
    """List of the colors of the palette as (r, g, b) that never runs out (index beyond the length gives further variants)"""

    def __getitem__(self, item):
        if isinstance(item, slice):
            return [paletteRgb(i) for i in range(*item.indices(max(item.stop or 0, len(PALETTE))))]
        return paletteRgb(int(item))

    def __len__(self):
        return len(PALETTE)


def paletteColormap():
    """Sequential colormap of the palette (purple, dark blue, cyan, teal, green, yellow) for maps, similar to viridis"""

    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list('hypercorporate', ['#685DA4', '#006699', '#00ADC1', '#00AD91', '#9BC437', '#FEC927'])


class Styles:
    """
    Style snippets for various PyQt objects
    """

    tu_blue_hex = '#006699'
    green_hex = '#5fbf64'
    red_hex = '#bf3e2f'
    orange_hex = '#d88f20'
    white_hex = '#FFFFFF'
    lightblue_hex = '#E8F4FF'
    lightgrey_hex = '#EEEEEE'
    darkgrey_hex = '#777777'

    title_style = f'''
        qproperty-alignment: AlignCenter;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        background-color: {tu_blue_hex};
        padding: 1px 5px;
        color: {white_hex};
    '''
    title_style_green = title_style.replace('#006699', green_hex)

    list_style = '''
        QListView::item {
            padding: 5px 5px;
        }
    '''

    # Note that the bracket is not closed until a color is added as well
    status_text_style = '''
        QLabel {
            font-size: 16px;
            font-weight: bold;
    '''
    green = f'color: {green_hex}; }}'
    red = f'color: {red_hex}; }}'
    orange = f'color: {orange_hex}; }}'

    search_style = f'''
        QLabel {{
            qproperty-alignment: AlignCenter;
            font-size: 25px;
            font-style: italic;
            color: #000000;
            background-color: {lightblue_hex};
        }}
    '''

    search_style_placeholder = f'''
        QLabel {{
            qproperty-alignment: AlignCenter;
            font-size: 25px;
            font-style: italic;
            color: {darkgrey_hex};
            background-color: {lightgrey_hex};
        }}
    '''
