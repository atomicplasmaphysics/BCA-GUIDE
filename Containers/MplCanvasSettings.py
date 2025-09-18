from typing import Tuple, Union

from Utility.Layouts import MplCanvas
from matplotlib import rc_context
from matplotlib.figure import Figure
from matplotlib.axes import Axes


class Logger:
    """
    Class for logging all function calls and variable assignments in a chronological list
    """

    def __init__(self):
        self._getattr_item = None
        self._calls = []

    def __getattr__(self, item):
        """Called if some attribute is accessed"""
        self._getattr_item = item
        return self._get_attr

    def __setattr__(self, key, value):
        """Called if some attribute is set"""
        if key in ['_getattr_item', '_calls']:
            super().__setattr__(key, value)
            return
        self._calls.append(('set', key, value))

    def _get_attr(self, *args, **kwargs):
        """Gets parameters passed to function"""
        self._calls.append(('func', self._getattr_item, args, kwargs))
        self._getattr_item = None
        return None

    def get_calls(self) -> list:
        """Returns list of all function calls and variable assignments"""
        return self._calls


class MplCanvasSettings:
    """
    Class that acts as container for settings that should be applied to the MplCanvas
    """

    def __init__(self):
        # Logger() has wrong data type, but the python editor will suggest hints for Figure and Axes
        self.fig: Union[Figure, Logger] = Logger()
        self.axes: Union[Axes, Logger] = Logger()
        pass

    def get_calls(self) -> Tuple[list, list]:
        """Returns list of all function calls and variable assignments for .fig and .axes"""
        return self.fig.get_calls(), self.axes.get_calls()

    def apply(self, canvas: MplCanvas):
        """
        Applies list of all function calls and variable assignments for .fig and .axes on a MplCanvas

        :param canvas: initialized MplCanvas() to draw to
        """

        # get all call lists
        fig_calls: list = self.fig.get_calls()
        axes_calls: list = self.axes.get_calls()

        with rc_context(canvas.get_rc_context()):
            # clear figure
            canvas.fig.clf()

            # initialize axes
            call_list = [f_c[1] for f_c in fig_calls]
            if 'add_subplot' in call_list:
                add_subplot_idx = call_list.index('add_subplot')
                canvas.axes = canvas.fig.add_subplot(*fig_calls[add_subplot_idx][2], **fig_calls[add_subplot_idx][3], **canvas.axes_kwargs, **canvas.palette_kwargs)
                del fig_calls[add_subplot_idx]
            else:
                canvas.axes = canvas.fig.add_subplot(projection='rectilinear', **canvas.palette_kwargs)

            # pcolormesh
            try:
                pcolormesh_idx = [a_c[1] for a_c in axes_calls].index('pcolormesh')
                pcolormesh = canvas.axes.pcolormesh(*axes_calls[pcolormesh_idx][2], **axes_calls[pcolormesh_idx][3])
                colorbar = canvas.fig.colorbar(pcolormesh)
                del axes_calls[pcolormesh_idx]

                # pcolormesh_label function = colorbar.set_label()
                try:
                    pcolormesh_label_idx = [a_c[1] for a_c in axes_calls].index('pcolormesh_label')
                    colorbar.set_label(*axes_calls[pcolormesh_label_idx][2], **axes_calls[pcolormesh_label_idx][3])
                    del axes_calls[pcolormesh_label_idx]

                except ValueError:
                    pass

            except ValueError:
                pass

            # apply all call lists
            # TODO: catch errors, print and reraise them
            for call in self.fig.get_calls():
                self.apply_call(canvas.fig, call)

            for call in self.axes.get_calls():
                # tick_params() overwrites labelcolor
                if call[0] == 'func' and call[1] == 'tick_params':
                    if not call[3].get('labelcolor'):
                        call[3]['labelcolor'] = canvas.fg_color
                self.apply_call(canvas.axes, call)

            # draw to canvas
            canvas.fig.tight_layout()
            canvas.fig.canvas.draw_idle()

    @staticmethod
    def apply_call(obj, call):
        """
        Applies specific function call or variable assignment to the object

        :param obj: object to be applied to
        :param call: call that is applied
        """

        if call[0] == 'func':
            func = getattr(obj, call[1])
            func(*call[2], **call[3])
        elif call[0] == 'set':
            setattr(obj, call[1], call[2])
