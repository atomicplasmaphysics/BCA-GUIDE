# BCA-GUIDE - a graphical user interface for bca simulations to simulate sputtering, ion implantation and the
# dynamic effects of ion irradiation
#
# Copyright(C) 2022, Alexander Redl, Paul S.Szabo, David Weichselbaum, Herbert Biber, Christian Cupak, Andreas Mutzke,
# Wolfhard Möller, Richard A.Wilhelm, Friedrich Aumayr
#
# This program implements libraries of the Qt framework (https://www.qt.io/).
#
# This program is free software: you can redistribute it and / or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. If not, see
# https://www.gnu.org/licenses/.


class Styles:
    """
    Style snippets for various PyQt objects
    """

    green_hex = '#5fbf64'
    red_hex = '#bf3e2f'
    orange_hex = '#d88f20'

    title_style = '''
        qproperty-alignment: AlignCenter;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        background-color: #006699;
        padding: 1px 5px;
        color: #FFFFFF;
    '''
    #   font-size: 14px; '''

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

    search_style = '''
        QLabel {
            qproperty-alignment: AlignCenter;
            font-size: 25px;
            font-style: italic;
            background-color: #E8F4FF;
        }
    '''

    search_style_placeholder = '''
        QLabel {
            qproperty-alignment: AlignCenter;
            font-size: 25px;
            font-style: italic;
            color: #777777;
            background-color: #EEEEEE;
        }
    '''
