#!/usr/bin/env python3
import sys
import numpy as np
from OpenGL import GL, GLU
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer


class OcclusionGLWidget(QOpenGLWidget):
    def __init__(self):
        super().__init__()
        self.plane_y = None
        self.test_points = []
        self.calculated_occlusion = []

        # orbital camera
        self.target = np.array([0.0, 0.0, 0.0])
        self.distance = 15.0
        self.azimuth = 45.0
        self.elevation = 25.0
        self.last_mouse_pos = None

    # ---------------- OpenGL ----------------

    def initializeGL(self):
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glClearColor(0.05, 0.05, 0.08, 1.0)

    def resizeGL(self, w, h):
        GL.glViewport(0, 0, w, h)

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        if self.plane_y is None:
            return
        self._setup_matrices()
        self._draw_plane()
        self._draw_points()

    # ---------------- Camera ----------------

    def _setup_matrices(self):
        w, h = self.width(), self.height()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GLU.gluPerspective(45.0, w / max(1, h), 0.1, 100.0)

        az, el = np.radians(self.azimuth), np.radians(self.elevation)
        self.camera_pos = np.array([
            self.distance * np.cos(el) * np.sin(az),
            self.distance * np.sin(el),
            self.distance * np.cos(el) * np.cos(az)
        ])

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GLU.gluLookAt(*self.camera_pos, *self.target, 0, 1, 0)

    # ---------------- Scene ----------------

    def _draw_plane(self, alpha=0.25):
        y, size = self.plane_y, 1000.0
        steps = 20
        step_size = size / steps

        # Translucent fill
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glColor4f(0.2, 0.6, 0.9, alpha)
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex3f(-size, y, -size)
        GL.glVertex3f( size, y, -size)
        GL.glVertex3f( size, y,  size)
        GL.glVertex3f(-size, y,  size)
        GL.glEnd()
        GL.glDisable(GL.GL_BLEND)

        # Wireframe
        GL.glColor3f(0.8, 0.8, 0.8)
        GL.glLineWidth(1.0)
        GL.glBegin(GL.GL_LINES)
        for i in range(-steps, steps + 1):
            x = i * step_size
            GL.glVertex3f(x, y, -size)
            GL.glVertex3f(x, y, size)
            z = i * step_size
            GL.glVertex3f(-size, y, z)
            GL.glVertex3f(size, y, z)
        GL.glEnd()

    def _draw_points(self):
        GL.glPointSize(8.0)
        GL.glBegin(GL.GL_POINTS)
        for p, occ in zip(self.test_points, self.calculated_occlusion):
            GL.glColor3f(1.0, 0.2, 0.2) if occ else GL.glColor3f(0.2, 1.0, 0.2)
            GL.glVertex3f(*p)
        GL.glEnd()

    # ---------------- Occlusion ----------------

    def run_occlusion_test(self):
        self.makeCurrent()
        self.calculated_occlusion.clear()
        modelview = GL.glGetDoublev(GL.GL_MODELVIEW_MATRIX)
        projection = GL.glGetDoublev(GL.GL_PROJECTION_MATRIX)
        viewport = GL.glGetIntegerv(GL.GL_VIEWPORT)

        for p in self.test_points:
            winx, winy, winz = GLU.gluProject(*p, modelview, projection, viewport)
            x, y, w, h = viewport
            px, py = int(winx), int(winy)

            if not (x <= px < x + w and y <= py < y + h):
                self.calculated_occlusion.append(True)
                continue

            GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
            depth = GL.glReadPixels(px, py, 1, 1, GL.GL_DEPTH_COMPONENT, GL.GL_FLOAT)
            self.calculated_occlusion.append(depth[0][0] < winz - 1e-6)

        self.update()

    # ---------------- Input ----------------

    def mousePressEvent(self, e):
        self.last_mouse_pos = e.pos()

    def mouseMoveEvent(self, e):
        if not self.last_mouse_pos:
            return
        dx, dy = e.x() - self.last_mouse_pos.x(), e.y() - self.last_mouse_pos.y()
        self.azimuth += dx * 0.5
        self.elevation = np.clip(self.elevation + dy * 0.5, -89, 89)
        self.last_mouse_pos = e.pos()
        self.update()

    def wheelEvent(self, e):
        self.distance *= 0.9 if e.angleDelta().y() > 0 else 1.1
        self.distance = np.clip(self.distance, 3.0, 50.0)
        self.update()

    # ---------------- Data ----------------

    def generate_test_data(self, n=20):
        np.random.seed(42)
        self.plane_y = np.random.uniform(-2, 2)
        self.test_points = [np.random.uniform(-5, 5, 3) for _ in range(n)]
        self.calculated_occlusion = [False] * n  # placeholder

    def showEvent(self, event):
        super().showEvent(event)
        if not any(self.calculated_occlusion):
            QTimer.singleShot(50, self.run_occlusion_test)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenGL Occlusion Debugger")

        self.gl = OcclusionGLWidget()
        self.gl.generate_test_data()

        btn = QPushButton("Run occlusion test")
        btn.clicked.connect(self.gl.run_occlusion_test)

        layout = QVBoxLayout(self)
        layout.addWidget(self.gl, 1)
        layout.addWidget(btn)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(900, 700)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
