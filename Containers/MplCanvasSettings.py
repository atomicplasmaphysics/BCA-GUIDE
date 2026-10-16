from typing import Tuple, Union, List, Optional
import logging

from Utility.Layouts import MplCanvas
from Utility.Functions import setDictIfNotExists

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

        # further axes (args and kwargs of fig.add_subplot, calls) and colorbars (mappable, kwargs, index of axes)
        self.extra_axes: List[Tuple[tuple, dict, Logger]] = []
        self.colorbars: List[Tuple[object, dict, int]] = []

    def addAxes(self, *args, **kwargs) -> Union[Axes, Logger]:
        """
        Adds a further axes (arguments of Figure.add_subplot) and returns its call logger.
        The first axes is self.axes (created with self.fig.add_subplot(...) or as a single axes)
        """

        axes = Logger()
        self.extra_axes.append((args, kwargs, axes))
        return axes

    def colorbar(self, mappable, axes_index: int = 0, **kwargs):
        """
        Adds a colorbar for a mappable (e.g. matplotlib.cm.ScalarMappable) next to an axes

        :param mappable: mappable of the colorbar
        :param axes_index: 0 for self.axes, 1... for the axes of addAxes()
        :param kwargs: arguments of Figure.colorbar (e.g. label, ticks)
        """

        self.colorbars.append((mappable, kwargs, axes_index))

    def get_calls(self) -> Tuple[list, list]:
        """Returns list of all function calls and variable assignments for .fig and .axes"""
        return self.fig.get_calls(), self.axes.get_calls()

    def apply(self, canvas: MplCanvas):
        """
        Applies list of all function calls and variable assignments for .fig and .axes on a MplCanvas

        :param canvas: initialized MplCanvas() to draw to
        """

        # get all call lists (copies, so that the settings can be applied more than once)
        fig_calls: list = list(self.fig.get_calls())
        axes_calls: list = list(self.axes.get_calls())

        # the view of a 3D plot is kept when it is redrawn (e.g. while animating)
        old_view: Optional[Tuple[float, float]] = None
        if getattr(canvas.axes, 'name', '') == '3d':
            old_view = (canvas.axes.elev, canvas.axes.azim)

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

            # further axes
            axes_list = [canvas.axes]
            for args, kwargs, _ in self.extra_axes:
                axes_list.append(canvas.fig.add_subplot(*args, **kwargs, **canvas.palette_kwargs))

            # apply all call lists
            for call in fig_calls:
                self.apply_call(canvas.fig, call)

            for axes, calls in zip(axes_list, [axes_calls] + [list(logger.get_calls()) for _, _, logger in self.extra_axes]):
                for call in calls:
                    # tick_params() overwrites labelcolor
                    if call[0] == 'func' and call[1] == 'tick_params':
                        setDictIfNotExists(call[3], 'labelcolor', canvas.fg_color)
                        if not call[3].get('labelcolor'):
                            call[3]['labelcolor'] = canvas.fg_color
                    self.apply_call(axes, call)

                if getattr(axes, 'name', '') == '3d':
                    if old_view is not None and not any(call[1] == 'view_init' for call in calls):
                        axes.view_init(*old_view)
                    # transparent panes, so that the background follows the theme
                    for axis in (axes.xaxis, axes.yaxis, axes.zaxis):
                        axis.set_pane_color((1., 1., 1., 0.))

            # colorbars
            for mappable, kwargs, index in self.colorbars:
                if 0 <= index < len(axes_list):
                    canvas.fig.colorbar(mappable, ax=axes_list[index], **kwargs)

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

        try:
            if call[0] == 'func':
                func = getattr(obj, call[1])
                func(*call[2], **call[3])
            elif call[0] == 'set':
                setattr(obj, call[1], call[2])
        except Exception as error:
            if call[0] == 'func':
                description = f'{call[1]}(args={call[2]}, kwargs={call[3]})'
            else:
                description = f'{call[1]} = {call[2]!r}'
            logging.error(f'Failed to apply "{description}" on <{type(obj).__name__}>: {error}')
            raise
