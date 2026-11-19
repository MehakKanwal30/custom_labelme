from PyQt5 import QtCore, QtGui, QtWidgets


class _Surface(QtWidgets.QWidget):
    """Paints a pixmap with the same scale/centering/flip rules as Canvas."""

    def __init__(self):
        super().__init__()
        self.pixmap = None
        self.scale = 1.0
        self.flip_h = False
        self.flip_v = False
        self.message = ""
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor(30, 30, 30))
        self.setPalette(pal)

    def sizeHint(self):
        if self.pixmap:
            return self.pixmap.size() * self.scale
        return super().sizeHint()

    minimumSizeHint = sizeHint

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        if not self.pixmap:
            p.setPen(QtGui.QColor(170, 170, 170))
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, self.message)
            p.end()
            return
        s = self.scale
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        ox = (self.width() - w) / (2 * s) if self.width() > w else 0
        oy = (self.height() - h) / (2 * s) if self.height() > h else 0
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        p.scale(s, s)
        p.translate(ox, oy)
        if self.flip_h or self.flip_v:
            p.translate(self.pixmap.width() if self.flip_h else 0,
                        self.pixmap.height() if self.flip_v else 0)
            p.scale(-1 if self.flip_h else 1, -1 if self.flip_v else 1)
        p.drawPixmap(0, 0, self.pixmap)
        p.end()


class ReferenceView(QtWidgets.QScrollArea):
    """Read-only pane showing a mask/overlay in lockstep with the main canvas."""

    def __init__(self, title):
        super().__init__()
        self.title = title
        self.surface = _Surface()
        self.setWidget(self.surface)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setMinimumWidth(120)
        self._center = (0.0, 0.0)  # image-space point to keep in the middle of this pane
        self.horizontalScrollBar().rangeChanged.connect(self._applyTarget)
        self.verticalScrollBar().rangeChanged.connect(self._applyTarget)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._applyTarget()  # pane resized by the splitter: re-centre, same zoom

    def _applyTarget(self, *_):
        s = self.surface
        if not s.pixmap:
            return
        vp = self.viewport()
        sc = s.scale
        # same centring rule as Canvas.offsetToCenter (surface is at least viewport-sized)
        w, h = s.pixmap.width() * sc, s.pixmap.height() * sc
        ox = (max(vp.width(), w) - w) / (2 * sc)
        oy = (max(vp.height(), h) - h) / (2 * sc)
        self.horizontalScrollBar().setValue(int((self._center[0] + ox) * sc - vp.width() / 2))
        self.verticalScrollBar().setValue(int((self._center[1] + oy) * sc - vp.height() / 2))

    def setPixmap(self, pixmap, message=""):
        """Show an already-rendered pixmap (same size as the image) or a message."""
        if pixmap is None or pixmap.isNull():
            self.surface.pixmap = None
            self.surface.message = message
        else:
            self.surface.pixmap = pixmap
        self.surface.updateGeometry()
        self.surface.update()

    def setImagePath(self, path):
        pm = QtGui.QPixmap(path) if path else QtGui.QPixmap()
        if pm.isNull():
            self.surface.pixmap = None
            self.surface.message = "No %s for this image" % self.title.lower()
        else:
            self.surface.pixmap = pm
        self.surface.updateGeometry()
        self.surface.update()

    def syncView(self, scale, flip_h, flip_v, center_x, center_y):
        """center_x/y: image-space point at the middle of the main view."""
        s = self.surface
        s.scale, s.flip_h, s.flip_v = scale, flip_h, flip_v
        s.updateGeometry()
        s.update()
        self._center = (center_x, center_y)
        self._applyTarget()
