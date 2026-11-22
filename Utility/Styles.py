from typing import Tuple


from PyQt6.QtGui import QColor


def hexToRgb(color: str) -> Tuple[float, float, float]:
    """
    Returns (r, g, b) in [0, 1] of a color

    :param color: color as '#RRGGBB'
    """

    color = color.lstrip('#')
    return int(color[0:2], 16) / 255, int(color[2:4], 16) / 255, int(color[4:6], 16) / 255


def paletteRgb(index: int) -> Tuple[float, float, float]:
    """
    Returns color of palette as (r, g, b) in [0, 1]: the 12 colors of the palette, then lightened, darkened and more
    lightened versions

    :param index: index of color
    """

    r, g, b = hexToRgb(Styles.palette[index % len(Styles.palette)])
    variant = (index // len(Styles.palette)) % 4
    if variant == 1:
        return r + 0.4 * (1 - r), g + 0.4 * (1 - g), b + 0.4 * (1 - b)
    if variant == 2:
        return 0.65 * r, 0.65 * g, 0.65 * b
    if variant == 3:
        return r + 0.65 * (1 - r), g + 0.65 * (1 - g), b + 0.65 * (1 - b)
    return r, g, b


def paletteHex(index: int) -> str:
    """
    Returns color of palette as '#rrggbb'

    :param index: index of color
    """

    return '#' + ''.join(f'{round(c * 255):02x}' for c in paletteRgb(index))


def layerHex(index: int) -> str:
    """
    Returns (lightened) color of a target layer as '#rrggbb'

    :param index: index of layer
    """

    return paletteHex(len(Styles.palette) + Styles.layer_colors[index % len(Styles.layer_colors)])


def paletteQColor(index: int, alpha: int = 255) -> QColor:
    """
    Returns color of palette as <QColor>

    :param index: index of color
    :param alpha: alpha value of color
    """

    color = QColor(paletteHex(index))
    color.setAlpha(alpha)
    return color


class Palette(list):
    """
    List of the colors of the palette as (r, g, b) that never runs out
    """

    def __getitem__(self, item):
        if isinstance(item, slice):
            return [paletteRgb(i) for i in range(*item.indices(max(item.stop or 0, len(Styles.palette))))]
        return paletteRgb(int(item))

    def __len__(self):
        return len(Styles.palette)


def paletteColormap():
    """Returns sequential colormap of the palette (purple, dark blue, cyan, teal, green, yellow)"""

    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(
        'hypercorporate',
        ['#685DA4', '#006699', '#00ADC1', '#00AD91', '#9BC437', '#FEC927']
    )


class Styles:
    """
    Style snippets for various PyQt objects
    """

    tu_blue_hex = '#006699'
    green_hex = '#5fbf64'
    red_hex = '#bf3e2f'
    orange_hex = '#d88f20'

    # colors of plots and elements (hypercorporateAF design)
    palette = [
        '#EA558F', '#F39345', '#FEC927', '#9BC437', '#00AD91', '#00ADC1',
        '#0084C2', '#006699', '#685DA4', '#9A5A9F', '#BD4492', '#CB2649'
    ]
    # first color of plots with one curve (blue) and colors of layers (yellow, teal, purple, orange, blue)
    first_color_index = 6
    layer_colors = [2, 4, 8, 1, 6]

    # accent colors of icons and previews as (light theme, dark theme)
    accent_colors = {
        'blue': (tu_blue_hex, '#4da6d9'),
        'green': ('#3f9f45', green_hex),
        'red': (red_hex, '#e5675a'),
        'orange': (orange_hex, '#f0a63a'),
    }
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
