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
