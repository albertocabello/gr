from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from matplotlib import __version__
from matplotlib.cbook import maxdict
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import RendererBase, GraphicsContextBase,\
    FigureManagerBase, FigureCanvasBase, register_backend
from matplotlib.path import Path
from matplotlib.figure import Figure
from matplotlib.mathtext import MathTextParser
from matplotlib.texmanager import TexManager

from os import putenv
import numpy as np
import gr


linetype = {'solid': 1, 'dashed': 2, 'dashdot': 4, 'dotted': 3}

putenv('GKS_DOUBLE_BUF', '1')


class RendererGR(RendererBase):
    """
    Handles drawing/rendering operations using GR
    """

    texd = maxdict(50)  # a cache of tex image rasters

    def __init__(self, dpi):
        self.dpi = dpi
        self.width = 640.0 * dpi / 80
        self.height = 480.0 * dpi / 80
        mwidth, mheight, width, height = gr.inqdspsize()
        if (width / (mwidth / 0.0256) < 200):
            mwidth *= self.width / width
            gr.setwsviewport(0, mwidth, 0, mwidth * 0.75)
        else:
            gr.setwsviewport(0, 0.192, 0, 0.144)
        gr.setwswindow(0, 1, 0, 0.75)
        gr.setviewport(0, 1, 0, 0.75)
        gr.setwindow(0, self.width, 0, self.height)
        self.mathtext_parser = MathTextParser('agg')
        self.texmanager = TexManager()

    def draw_path(self, gc, path, transform, rgbFace=None):
        path = transform.transform_path(path)
        points = path.vertices
        codes = path.codes
        bbox = gc.get_clip_rectangle()
        if bbox is not None:
            x, y, w, h = bbox.bounds
            clrt = np.array([x, x + w, y, y + h])
        else:
            clrt = np.array([0, self.width, 0, self.height])
        gr.setviewport(*clrt/self.width)
        gr.setwindow(*clrt)
        if rgbFace is not None and len(points) > 2:
            color = gr.inqcolorfromrgb(rgbFace[0], rgbFace[1], rgbFace[2])
            gr.settransparency(rgbFace[3])
            gr.setcolorrep(color, rgbFace[0], rgbFace[1], rgbFace[2])
            gr.setfillintstyle(gr.INTSTYLE_SOLID)
            gr.setfillcolorind(color)
            gr.drawpath(points, codes, fill=True)
        lw = gc.get_linewidth()
        if lw != 0:
            rgba = gc.get_rgb()[:4]
            color = gr.inqcolorfromrgb(rgba[0], rgba[1], rgba[2])
            gr.settransparency(rgba[3])
            gr.setcolorrep(color, rgba[0], rgba[1], rgba[2])
            if type(gc._linestyle) is unicode:
                gr.setlinetype(linetype[gc._linestyle])
            gr.setlinewidth(lw)
            gr.setlinecolorind(color)
            gr.drawpath(points, codes, fill=False)

    def draw_image(self, gc, x, y, im):
        h, w, s = im.as_rgba_str()
        img = np.fromstring(s, np.uint32)
        img.shape = (h, w)
        gr.drawimage(x, x + w, y + h, y, w, h, img)

    def draw_mathtext(self, x, y, angle, Z):
        h, w = Z.shape
        img = np.zeros((h, w), np.uint32)
        for i in range(h):
            for j in range(w):
                img[i, j] = (255 - Z[i, j]) << 24
        a = int(angle)
        if a == 90:
            gr.drawimage(x - h, x, y, y + w, h, w,
                         np.resize(np.rot90(img, 1), (h, w)))
        elif a == 180:
            gr.drawimage(x - w, x, y - h, y, w, h, np.rot90(img, 2))
        elif a == 270:
            gr.drawimage(x, x + h, y - w, y, h, w,
                         np.resize(np.rot90(img, 3), (h, w)))
        else:
            gr.drawimage(x, x + w, y, y + h, w, h, img)

    def draw_tex(self, gc, x, y, s, prop, angle, ismath='TeX!', mtext=None):
        size = prop.get_size_in_points()
        key = s, size, self.dpi, angle, self.texmanager.get_font_config()
        im = self.texd.get(key)
        if im is None:
            Z = self.texmanager.get_grey(s, size, self.dpi)
            Z = np.array(255.0 - Z * 255.0, np.uint8)

        self.draw_mathtext(x, y, angle, Z)

    def _draw_mathtext(self, gc, x, y, s, prop, angle):
        ox, oy, width, height, descent, image, used_characters = \
            self.mathtext_parser.parse(s, self.dpi, prop)
        self.draw_mathtext(x, y, angle, 255 - image.as_array())

    def draw_text(self, gc, x, y, s, prop, angle, ismath=False, mtext=None):
        if ismath:
            self._draw_mathtext(gc, x, y, s, prop, angle)
        else:
            x, y = gr.wctondc(x, y)
            s = s.replace(u'\u2212', '-')
            fontsize = prop.get_size_in_points()
            rgba = gc.get_rgb()[:4]
            color = gr.inqcolorfromrgb(rgba[0], rgba[1], rgba[2])
            gr.settransparency(rgba[3])
            gr.setcolorrep(color, rgba[0], rgba[1], rgba[2])
            gr.setcharheight(fontsize * 0.0013)
            gr.settextcolorind(color)
            if angle != 0:
                gr.setcharup(-np.sin(angle * np.pi/180),
                             np.cos(angle * np.pi/180))
            else:
                gr.setcharup(0, 1)
            gr.text(x, y, s.encode("latin-1"))

    def flipy(self):
        return False

    def get_canvas_width_height(self):
        return self.width, self.height

    def get_text_width_height_descent(self, s, prop, ismath):
        if ismath == 'TeX':
            fontsize = prop.get_size_in_points()
            w, h, d = self.texmanager.get_text_width_height_descent(
                s, fontsize, renderer=self)
            return w, h, d
        if ismath:
            ox, oy, width, height, descent, fonts, used_characters = \
                self.mathtext_parser.parse(s, self.dpi, prop)
            return width, height, descent
#       family =  prop.get_family()
#       weight = prop.get_weight()
#       style = prop.get_style()
        s = s.replace(u'\u2212', '-').encode("latin-1")
        fontsize = prop.get_size_in_points()
        gr.setcharheight(fontsize * 0.0013)
        gr.setcharup(0, 1)
        (tbx, tby) = gr.inqtextext(0, 0, s)
        width, height, descent = tbx[1], tby[2], 0
        return width, height, descent

    def new_gc(self):
        return GraphicsContextGR()

    def points_to_pixels(self, points):
        return points


class GraphicsContextGR(GraphicsContextBase):
    pass


def draw_if_interactive():
    pass


def show():
    for manager in Gcf.get_all_fig_managers():
        manager.show()


def new_figure_manager(num, *args, **kwargs):
    """
    Create a new figure manager instance
    """
    FigureClass = kwargs.pop('FigureClass', Figure)
    thisFig = FigureClass(*args, **kwargs)
    return new_figure_manager_given_figure(num, thisFig)


def new_figure_manager_given_figure(num, figure):
    """
    Create a new figure manager instance for the given figure.
    """
    canvas = FigureCanvasGR(figure)
    manager = FigureManagerGR(canvas, num)
    return manager


class FigureCanvasGR(FigureCanvasBase):
    """
    The canvas the figure renders into.  Calls the draw and print fig
    methods, creates the renderers, etc...
    """

    if __version__ >= '1.4':
        register_backend('gr', 'backend_gr', 'GR File Format')
    else:
        register_backend('gr', 'backend_gr')

    def draw(self):
        """
        Draw the figure using the renderer
        """
        gr.clearws()
        renderer = RendererGR(self.figure.dpi)
        self.figure.draw(renderer)
        gr.updatews()

    def print_gr(self, filename, *args, **kwargs):
        gr.begingraphics(filename)
        self.draw()
        gr.endgraphics()


class FigureManagerGR(FigureManagerBase):
    """
    Wrap everything up into a window for the pylab interface
    """
    def show(self):
        canvas = FigureCanvasGR(self.canvas.figure)
        FigureCanvasGR.draw(canvas)


FigureCanvas = FigureCanvasGR
FigureManager = FigureManagerGR
