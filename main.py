import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QToolBar, QAction, QMessageBox, QColorDialog, QSlider, QSpinBox, QDockWidget
)
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QImage, QPixmap, QMouseEvent, QKeySequence, QTransform
from PyQt5.QtCore import Qt, QPoint, QRect

# Mode operasi canvas


class Mode:
    BRUSH = 'brush'
    LINE = 'line'
    RECT = 'rect'
    CIRCLE = 'circle'
    FILL = 'fill'
    SELECT = 'select'
    MOVE = 'move'
    ROTATE = 'rotate'
    SCALE = 'scale'

# Widget Canvas utama


class Canvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_size = (800, 600)
        self.setMinimumSize(*self.base_size)
        self.image = QImage(*self.base_size, QImage.Format_ARGB32)
        self.image.fill(Qt.white)
        self.drawing = False
        self.last_point = QPoint()
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.mode = Mode.BRUSH
        self.brush_color = Qt.black
        self.brush_size = 3
        self.stroke_size = 3
        self.undo_stack = []
        self.redo_stack = []
        self.selection_rect = QRect()
        self.selected_image = None
        self.transforming = False
        self.flood_fill_type = 4
        self.zoom = 1.0
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._drag_offset = QPoint()
        self._rot_angle = 0
        self._scale_factor = 1.0
        self._pan = QPoint(0, 0)  # Camera offset
        self._panning = False
        self._pan_start = QPoint()
        self._pan_origin = QPoint()
        self._move_offset = QPoint(0, 0)  # Offset untuk move

    def set_mode(self, mode):
        self.mode = mode
        if mode != Mode.SELECT:
            self.selection_rect = QRect()
            self.selected_image = None
            self.transforming = False
        self.update()

    def set_brush_color(self, color):
        self.brush_color = color
        self.update()

    def set_brush_size(self, size):
        self.brush_size = size
        self.stroke_size = size
        self.update()

    def set_stroke_size(self, size):
        self.stroke_size = size
        self.update()

    def set_flood_fill_type(self, t):
        self.flood_fill_type = t

    def set_zoom(self, zoom):
        self.zoom = max(0.1, min(zoom, 16.0))
        self.update()

    def clear(self):
        self._push_undo()
        self.image.fill(Qt.white)
        self.update()

    def save_image(self, path):
        self.image.save(path)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.image.copy())
            self.image = self.undo_stack.pop()
            self.update()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.image.copy())
            self.image = self.redo_stack.pop()
            self.update()

    def _push_undo(self):
        self.undo_stack.append(self.image.copy())
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def mousePressEvent(self, event):
        img_pos = self._to_image_pos(event.pos())
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self._pan_origin = self._pan
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.LeftButton:
            if self.mode == Mode.SELECT:
                # Mulai select baru
                self.selection_rect = QRect(img_pos, img_pos)
                self.selected_image = None
                self.drawing = True
                self._select_committed = False
            elif self.mode in [Mode.MOVE, Mode.ROTATE, Mode.SCALE]:
                # Hanya bisa transform jika ada selected_image
                if self.selected_image is not None:
                    self.transforming = True
                    self.last_point = img_pos
            elif self.mode == Mode.LINE:
                self._push_undo()
                self.drawing = True
                self.start_point = img_pos
                self.end_point = img_pos
            else:
                self._push_undo()
                self.drawing = True
                self.last_point = img_pos
                self.start_point = img_pos
                if self.mode == Mode.FILL:
                    self.flood_fill(img_pos)
                    self.drawing = False
            self.update()

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan = self._pan_origin + delta
            self.update()
            return
        img_pos = self._to_image_pos(event.pos())
        if self.mode == Mode.BRUSH and self.drawing:
            painter = QPainter(self.image)
            pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self.last_point, img_pos)
            self.last_point = img_pos
            self.update()
        elif self.mode == Mode.LINE and self.drawing:
            self.end_point = img_pos
            self.update()
        elif self.mode in [Mode.RECT, Mode.CIRCLE] and self.drawing:
            self.end_point = img_pos
            self.update()
        elif self.mode == Mode.SELECT and self.drawing:
            self.end_point = img_pos
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()
        elif self.mode == Mode.MOVE and self.transforming and self.selected_image is not None:
            delta = img_pos - self.last_point
            self._move_offset += delta
            self.last_point = img_pos
            self.update()
        elif self.mode == Mode.ROTATE and self.transforming and self.selected_image is not None:
            center = self.selection_rect.center()
            dx = img_pos.x() - center.x()
            dy = img_pos.y() - center.y()
            self._rot_angle = (dx + dy) % 360
            self.update()
        elif self.mode == Mode.SCALE and self.transforming and self.selected_image is not None:
            rect = self.selection_rect
            width = max(1, img_pos.x() - rect.left())
            height = max(1, img_pos.y() - rect.top())
            self._scale_factor = min(width / rect.width(), height / rect.height())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
        img_pos = self._to_image_pos(event.pos())
        if event.button() == Qt.LeftButton:
            if self.mode == Mode.BRUSH:
                self.drawing = False
            elif self.mode == Mode.LINE and self.drawing:
                painter = QPainter(self.image)
                pen = QPen(self.brush_color, self.stroke_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(self.start_point, img_pos)
                self.drawing = False
                self.update()
            elif self.mode == Mode.RECT and self.drawing:
                painter = QPainter(self.image)
                pen = QPen(self.brush_color, self.stroke_size)
                painter.setPen(pen)
                painter.drawRect(QRect(self.start_point, img_pos))
                self.drawing = False
                self.update()
            elif self.mode == Mode.CIRCLE and self.drawing:
                painter = QPainter(self.image)
                pen = QPen(self.brush_color, self.stroke_size)
                painter.setPen(pen)
                painter.drawEllipse(QRect(self.start_point, img_pos))
                self.drawing = False
                self.update()
            elif self.mode == Mode.SELECT and self.drawing:
                self.drawing = False
                self.selection_rect = self.selection_rect.normalized()
                if self.selection_rect.isValid() and self.selection_rect.width() > 0 and self.selection_rect.height() > 0:
                    # Simpan snapshot area, kosongkan area aslinya (seperti cut/floating selection)
                    self.selected_image = self.image.copy(self.selection_rect)
                    # Kosongkan area asli (floating selection)
                    painter = QPainter(self.image)
                    painter.setCompositionMode(QPainter.CompositionMode_Source)
                    painter.fillRect(self.selection_rect, Qt.transparent)
                    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    self._move_offset = QPoint(0, 0)
                    self._rot_angle = 0
                    self._scale_factor = 1.0
                    self._select_committed = False
                    self.set_mode(Mode.MOVE)  # Otomatis masuk mode move
                self.update()
            elif self.mode in [Mode.MOVE, Mode.ROTATE, Mode.SCALE] and self.transforming:
                self.transforming = False
                self.update()

    def wheelEvent(self, event):
        # Zoom with scrollwheel, centered at mouse
        old_zoom = self.zoom
        if event.angleDelta().y() > 0:
            self.zoom = min(self.zoom * 1.1, 16.0)
        else:
            self.zoom = max(self.zoom / 1.1, 0.1)
        # Adjust pan so that zoom centers at mouse
        mouse_pos = event.pos()
        before = (mouse_pos - self._pan) / old_zoom
        after = (mouse_pos - self._pan) / self.zoom
        self._pan += (after - before) * self.zoom
        self.update()

    def resizeEvent(self, event):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        offset = self._canvas_offset() + self._pan
        scaled = self.image.scaled(self.zoomed_size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawImage(offset, scaled)
        # Draw temp shapes (rect/circle/line/selection) in widget coordinates
        if self.drawing and self.mode in [Mode.RECT, Mode.CIRCLE, Mode.LINE]:
            pen = QPen(self.brush_color, self.stroke_size * self.zoom, Qt.DashLine)
            painter.setPen(pen)
            if self.mode == Mode.LINE:
                painter.drawLine(self._to_widget(self.start_point), self._to_widget(self.end_point))
            else:
                rect = QRect(self.start_point, self.end_point)
                widget_rect = self._to_widget_rect(rect)
                if self.mode == Mode.RECT:
                    painter.drawRect(widget_rect)
                elif self.mode == Mode.CIRCLE:
                    painter.drawEllipse(widget_rect)
        # Draw floating selection
        if self.selected_image is not None and self.selection_rect.isValid():
            sel_rect = self.selection_rect.translated(self._move_offset)
            widget_rect = self._to_widget_rect(sel_rect)
            img = self.selected_image
            if self.mode == Mode.ROTATE:
                transform = QTransform()
                center = img.rect().center()
                transform.translate(center.x(), center.y())
                transform.rotate(self._rot_angle)
                transform.translate(-center.x(), -center.y())
                img = img.transformed(transform, Qt.SmoothTransformation)
            elif self.mode == Mode.SCALE:
                w = int(img.width() * self._scale_factor)
                h = int(img.height() * self._scale_factor)
                img = img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawImage(widget_rect.topLeft(), img)
            # Draw selection border
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(widget_rect)

    def apply_transform(self):
        # Commit floating selection ke image
        if self.selected_image is not None and self.selection_rect.isValid():
            painter = QPainter(self.image)
            img = self.selected_image
            # Transformasi
            if self.mode == Mode.ROTATE:
                transform = QTransform()
                center = img.rect().center()
                transform.translate(center.x(), center.y())
                transform.rotate(self._rot_angle)
                transform.translate(-center.x(), -center.y())
                img = img.transformed(transform, Qt.SmoothTransformation)
            elif self.mode == Mode.SCALE:
                w = int(img.width() * self._scale_factor)
                h = int(img.height() * self._scale_factor)
                img = img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # Move offset
            target_rect = self.selection_rect.translated(self._move_offset)
            # Clear area
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(target_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawImage(target_rect.topLeft(), img)
            # Reset selection
            self.selected_image = None
            self.selection_rect = QRect()
            self._move_offset = QPoint(0, 0)
            self._rot_angle = 0
            self._scale_factor = 1.0
            self._select_committed = True
            self.update()

    def flood_fill(self, pos):
        # Flood fill (4-connected or 8-connected)
        x, y = pos.x(), pos.y()
        if x < 0 or y < 0 or x >= self.image.width() or y >= self.image.height():
            return
        target_color = QColor(self.image.pixel(x, y))
        fill_color = QColor(self.brush_color)
        if target_color == fill_color:
            return
        w, h = self.image.width(), self.image.height()
        stack = [(x, y)]
        visited = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            if cx < 0 or cy < 0 or cx >= w or cy >= h:
                continue
            if QColor(self.image.pixel(cx, cy)) != target_color:
                continue
            self.image.setPixel(cx, cy, fill_color.rgb())
            visited.add((cx, cy))
            stack.extend(self._get_neighbors(cx, cy, self.flood_fill_type))
        self.update()

    def _get_neighbors(self, x, y, t):
        # t: 4 or 8 connected
        neighbors = [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]
        if t == 8:
            neighbors += [(x-1, y-1), (x+1, y-1), (x-1, y+1), (x+1, y+1)]
        return neighbors

    def _to_image_pos(self, widget_pos):
        # Convert widget pos to image pos, considering pan and zoom
        offset = self._canvas_offset() + self._pan
        x = int((widget_pos.x() - offset.x()) / self.zoom)
        y = int((widget_pos.y() - offset.y()) / self.zoom)
        return QPoint(x, y)

    def _to_widget_rect(self, img_rect):
        offset = self._canvas_offset() + self._pan
        x = int(img_rect.left() * self.zoom + offset.x())
        y = int(img_rect.top() * self.zoom + offset.y())
        w = int(img_rect.width() * self.zoom)
        h = int(img_rect.height() * self.zoom)
        return QRect(x, y, w, h)

    def _to_widget(self, img_point):
        offset = self._canvas_offset() + self._pan
        x = int(img_point.x() * self.zoom + offset.x())
        y = int(img_point.y() * self.zoom + offset.y())
        return QPoint(x, y)

    def _canvas_offset(self):
        # Center the image in the widget
        sz = self.zoomed_size()
        x = (self.width() - sz.width()) // 2
        y = (self.height() - sz.height()) // 2
        return QPoint(x, y)

    def zoomed_size(self):
        return self.image.size() * self.zoom

# Main Window


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('MiniPaint')
        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self._create_sidebar()
        self._create_shortcuts()
        self.statusBar().showMessage('Ready')
        self.showMaximized()

    def _create_sidebar(self):
        dock = QDockWidget('Tools', self)
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        dock.setTitleBarWidget(QWidget())
        sidebar = QWidget()
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        # Tool buttons

        def add_btn(text, cb):
            btn = QPushButton(text)
            btn.clicked.connect(cb)
            btn.setFixedWidth(80)
            layout.addWidget(btn)
            return btn
        add_btn('Brush', lambda: self.set_mode(Mode.BRUSH))
        add_btn('Line', lambda: self.set_mode(Mode.LINE))
        add_btn('Rect', lambda: self.set_mode(Mode.RECT))
        add_btn('Circle', lambda: self.set_mode(Mode.CIRCLE))
        add_btn('Fill', lambda: self.set_mode(Mode.FILL))
        add_btn('Select', lambda: self.set_mode(Mode.SELECT))
        add_btn('Move', lambda: self.set_mode(Mode.MOVE))
        add_btn('Rotate', lambda: self.set_mode(Mode.ROTATE))
        add_btn('Scale', lambda: self.set_mode(Mode.SCALE))
        add_btn('Undo', self.canvas.undo)
        add_btn('Redo', self.canvas.redo)
        add_btn('Clear', self.canvas.clear)
        add_btn('Save', self.save_canvas)
        # Fill type
        add_btn('Fill 4', lambda: self.canvas.set_flood_fill_type(4))
        add_btn('Fill 8', lambda: self.canvas.set_flood_fill_type(8))
        add_btn('Apply', self.canvas.apply_transform)
        # Color picker
        color_btn = QPushButton('Color')
        color_btn.clicked.connect(self.pick_color)
        layout.addWidget(color_btn)
        # Brush size
        layout.addWidget(QLabel('Brush Size'))
        brush_slider = QSlider(Qt.Horizontal)
        brush_slider.setRange(1, 50)
        brush_slider.setValue(self.canvas.brush_size)
        brush_slider.valueChanged.connect(self.canvas.set_brush_size)
        layout.addWidget(brush_slider)
        # Stroke size
        layout.addWidget(QLabel('Stroke Size'))
        stroke_slider = QSlider(Qt.Horizontal)
        stroke_slider.setRange(1, 50)
        stroke_slider.setValue(self.canvas.stroke_size)
        stroke_slider.valueChanged.connect(self.canvas.set_stroke_size)
        layout.addWidget(stroke_slider)
        # Zoom
        layout.addWidget(QLabel('Zoom'))
        zoom_slider = QSlider(Qt.Horizontal)
        zoom_slider.setRange(1, 400)
        zoom_slider.setValue(int(self.canvas.zoom * 100))
        zoom_slider.valueChanged.connect(
            lambda v: self.canvas.set_zoom(v / 100))
        layout.addWidget(zoom_slider)
        layout.addStretch(1)
        dock.setWidget(sidebar)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _create_shortcuts(self):
        self.canvas.setFocusPolicy(Qt.StrongFocus)
        self.shortcut_map = {
            Qt.Key_B: Mode.BRUSH,
            Qt.Key_R: Mode.RECT,
            Qt.Key_C: Mode.CIRCLE,
            Qt.Key_F: Mode.FILL,
            Qt.Key_S: Mode.SELECT,
            Qt.Key_M: Mode.MOVE,
            Qt.Key_T: Mode.ROTATE,
            Qt.Key_E: Mode.SCALE,
            Qt.Key_Z: 'undo',
            Qt.Key_Y: 'redo',
            Qt.Key_X: 'clear',
            Qt.Key_P: 'save',
            Qt.Key_Plus: 'zoom_in',
            Qt.Key_Minus: 'zoom_out',
        }

    def keyPressEvent(self, event):
        key = event.key()
        if key in self.shortcut_map:
            action = self.shortcut_map[key]
            if action in [Mode.BRUSH, Mode.RECT, Mode.CIRCLE, Mode.FILL, Mode.SELECT, Mode.MOVE, Mode.ROTATE, Mode.SCALE]:
                self.set_mode(action)
            elif action == 'undo':
                self.canvas.undo()
            elif action == 'redo':
                self.canvas.redo()
            elif action == 'clear':
                self.canvas.clear()
            elif action == 'save':
                self.save_canvas()
            elif action == 'zoom_in':
                self.canvas.set_zoom(self.canvas.zoom * 1.1)
            elif action == 'zoom_out':
                self.canvas.set_zoom(self.canvas.zoom / 1.1)

    def set_mode(self, mode):
        self.canvas.set_mode(mode)
        self.statusBar().showMessage(f'Mode: {mode}')

    def save_canvas(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Image', '', 'PNG Files (*.png)')
        if path:
            self.canvas.save_image(path)
            QMessageBox.information(self, 'Saved', f'Image saved to {path}')

    def pick_color(self):
        color = QColorDialog.getColor(
            self.canvas.brush_color, self, 'Pick Color')
        if color.isValid():
            self.canvas.set_brush_color(color)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
