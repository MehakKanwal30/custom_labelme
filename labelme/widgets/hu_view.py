from PyQt5 import QtCore, QtGui, QtWidgets

from .canvas import Canvas


# Canvas state the HU canvas borrows from the main canvas so it paints exactly what the
# main canvas would: shapes, selection, the shape being drawn, modes, overlays...
_BORROWED = (
    "mode", "_createMode", "shapes", "visible", "selectedShapes", "selectedShapesCopy",
    "current", "line", "prevPoint", "prevMovePoint", "_hideBackround", "hideBackround",
    "selected_shape_priority", "show_pixel_grid", "show_original", "snapping",
    "splitMode", "splitPicks", "_paint_mask", "_paint_overlay", "hShape", "hVertex",
    "hEdge", "epsilon", "flip_horizontal", "flip_vertical", "lasso_step",
)


class HuCanvas(Canvas):
    """A second view of the main canvas showing the HU-windowed image.

    It is fully interactive, but all the logic stays in the main canvas: mouse and key
    events here are converted to the same image position on the main canvas and handed
    to it. Drawing (polygon, rectangle, lasso, pixel paint...), selecting, moving
    points and shapes, splitting, right-click menus, undo and every mode therefore work
    here exactly as in the main window. This canvas only paints."""

    def __init__(self, source, **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.menus = source.menus  # same right-click menus as the main canvas

    # -- painting ----------------------------------------------------------------

    def _borrow(self):
        for name in _BORROWED:
            if hasattr(self.source, name):
                setattr(self, name, getattr(self.source, name))

    def paintEvent(self, event):
        self._borrow()
        super().paintEvent(event)

    # -- forwarding ---------------------------------------------------------------

    def _ready(self):
        return not self.pixmap.isNull() and not self.source.pixmap.isNull()

    def _to_source(self, pos):
        """Same image point, in main-canvas widget coordinates."""
        s = self.scale
        here, there = self.offsetToCenter(), self.source.offsetToCenter()
        return QtCore.QPointF(pos.x() + (there.x() - here.x()) * s, pos.y() + (there.y() - here.y()) * s)

    def _forward_mouse(self, ev, handler_name):
        if not self._ready():
            return
        self._borrow()
        mapped = QtGui.QMouseEvent(
            ev.type(), self._to_source(ev.localPos()), ev.windowPos(), ev.screenPos(),
            ev.button(), ev.buttons(), ev.modifiers())
        getattr(self.source, handler_name)(mapped)

    def mousePressEvent(self, ev):
        self._forward_mouse(ev, "mousePressEvent")

    def mouseMoveEvent(self, ev):
        self._forward_mouse(ev, "mouseMoveEvent")

    def mouseDoubleClickEvent(self, ev):
        self._forward_mouse(ev, "mouseDoubleClickEvent")

    def mouseReleaseEvent(self, ev):
        if not self._ready():
            return
        if ev.button() == QtCore.Qt.RightButton:
            # the context menu belongs under the cursor in this pane, not the main one
            src = self.source
            menu = src.menus[len(src.selectedShapesCopy) > 0]
            src.restoreCursor()
            if not menu.exec_(ev.globalPos()) and src.selectedShapesCopy:
                src.selectedShapesCopy = []
                src.repaint()
            return
        self._forward_mouse(ev, "mouseReleaseEvent")

    def keyPressEvent(self, ev):
        self._borrow()
        self.source.keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        self._borrow()
        self.source.keyReleaseEvent(ev)

    def enterEvent(self, ev):
        self.source.enterEvent(ev)

    def leaveEvent(self, ev):
        self.source.leaveEvent(ev)

    def focusOutEvent(self, ev):
        self.source.focusOutEvent(ev)


class _PaintForwarder(QtCore.QObject):
    """Repaint the HU canvas whenever the main canvas repaints.

    Kept separate from HuView: QScrollArea relies on its own eventFilter to track the
    size of its widget, so HuView must not override it."""

    def __init__(self, target):
        super().__init__(target)
        self.target = target

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Paint:
            self.target.update()
        return False


class HuView(QtWidgets.QScrollArea):
    """Pane holding the HU canvas; zoom, flips and scroll follow the main view."""

    def __init__(self, source, **canvas_kwargs):
        super().__init__()
        self.source = source
        self.canvas = HuCanvas(source, **canvas_kwargs)
        self.setWidget(self.canvas)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setMinimumWidth(120)
        self._center = (0.0, 0.0)
        self.message = QtWidgets.QLabel(self.viewport())
        self.message.setAlignment(QtCore.Qt.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.horizontalScrollBar().rangeChanged.connect(self._applyTarget)
        self.verticalScrollBar().rangeChanged.connect(self._applyTarget)
        self._forwarder = _PaintForwarder(self.canvas)
        source.installEventFilter(self._forwarder)  # repaint when the main canvas repaints

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.message.setGeometry(self.viewport().rect())
        self._applyTarget()

    def hasImage(self):
        return not self.canvas.pixmap.isNull()

    def setHuPixmap(self, pixmap, message=""):
        if pixmap is None or pixmap.isNull():
            self.canvas.pixmap = QtGui.QPixmap()
            self.message.setText(message)
            self.message.show()
        else:
            self.canvas.loadPixmap(pixmap, clear_shapes=False)
            self.canvas.pixmap_original = QtGui.QPixmap(pixmap)  # "Show Original" paints this
            self.message.hide()
        self.canvas.updateGeometry()
        self.canvas.update()

    def _applyTarget(self, *_):
        c = self.canvas
        if c.pixmap.isNull():
            return
        vp = self.viewport()
        sc = c.scale
        w, h = c.pixmap.width() * sc, c.pixmap.height() * sc
        ox = (max(vp.width(), w) - w) / (2 * sc)
        oy = (max(vp.height(), h) - h) / (2 * sc)
        self.horizontalScrollBar().setValue(int((self._center[0] + ox) * sc - vp.width() / 2))
        self.verticalScrollBar().setValue(int((self._center[1] + oy) * sc - vp.height() / 2))

    def syncView(self, scale, flip_h, flip_v, center_x, center_y):
        c = self.canvas
        c.scale = scale
        c.flip_horizontal, c.flip_vertical = flip_h, flip_v
        if not c.pixmap.isNull():
            c.adjustSize()
        c.update()
        self._center = (center_x, center_y)
        self._applyTarget()
