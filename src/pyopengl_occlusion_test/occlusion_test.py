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

        # Orbital camera
        self.target = np.zeros(3)
        self.distance = 15.0
        self.azimuth = 45.0
        self.elevation = 25.0
        self.last_mouse_pos = None
        self._pending_occlusion_test = True

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
        aspect = self.width() / max(1, self.height())
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GLU.gluPerspective(45.0, aspect, 0.1, 100.0)

        # Spherical → Cartesian
        az = np.radians(self.azimuth)
        el = np.radians(self.elevation)
        cam_x = self.distance * np.cos(el) * np.sin(az)
        cam_y = self.distance * np.sin(el)
        cam_z = self.distance * np.cos(el) * np.cos(az)
        self.camera_pos = np.array([cam_x, cam_y, cam_z])

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GLU.gluLookAt(cam_x, cam_y, cam_z, *self.target, 0, 1, 0)

    # ---------------- Scene ----------------

    def _draw_plane(self):
        y = self.plane_y
        size = 1000.0
        steps = 20
        step_size = size / steps

        # Translucent fill
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glColor4f(0.2, 0.6, 0.9, 0.35)
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex3f(-size, y, -size)
        GL.glVertex3f( size, y, -size)
        GL.glVertex3f( size, y,  size)
        GL.glVertex3f(-size, y,  size)
        GL.glEnd()
        GL.glDisable(GL.GL_BLEND)

        # Wireframe grid
        GL.glColor3f(0.8, 0.8, 0.8)
        GL.glLineWidth(1.0)
        GL.glBegin(GL.GL_LINES)
        for i in range(-steps, steps + 1):
            x = i * step_size
            GL.glVertex3f(x, y, -size)
            GL.glVertex3f(x, y,  size)
            z = i * step_size
            GL.glVertex3f(-size, y, z)
            GL.glVertex3f( size, y, z)
        GL.glEnd()

    def _draw_points(self, not_draw=False):
        if not_draw:
            return
        GL.glPointSize(8.0)
        GL.glBegin(GL.GL_POINTS)
        for p, occ in zip(self.test_points, self.calculated_occlusion):
            GL.glColor3f(0.2, 1.0, 0.2) if occ else GL.glColor3f(1.0, 0.2, 0.2)
            GL.glVertex3f(*p)
        GL.glEnd()

    # ---------------- Occlusion logic ----------------

    def request_occlusion_test(self):
        self._pending_occlusion_test = True
        self.update()  # trigger repaint

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        if self.plane_y is None:
            return

        self._setup_matrices()

        self._draw_plane()

        if self._pending_occlusion_test:
            self._pending_occlusion_test = False
            self.calculated_occlusion = list(self._run_occlusion_queries(self.test_points))
            print("="*25)
            for idx, passed in enumerate(self.calculated_occlusion):
                print(f"Point {idx:02d}: {'Occluded' if not passed else 'Visible'}")

        self._draw_points()  # Don't write depth/color, just visualize


    def _run_occlusion_queries(self, points):
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(False)
        GL.glColorMask(False, False, False, False)
        GL.glPointSize(1.0)

        for p in points:
            query = GL.glGenQueries(1)[0]

            GL.glBeginQuery(GL.GL_ANY_SAMPLES_PASSED, query)

            GL.glBegin(GL.GL_POINTS)
            GL.glVertex3f(*p)
            GL.glEnd()

            GL.glEndQuery(GL.GL_ANY_SAMPLES_PASSED)

            yield bool(GL.glGetQueryObjectuiv(query, GL.GL_QUERY_RESULT))

            GL.glDeleteQueries(1, [query])

        GL.glColorMask(True, True, True, True)
        GL.glDepthMask(True)


    # ---------------- Input ----------------

    def mousePressEvent(self, e):
        self.last_mouse_pos = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self.last_mouse_pos is None:
            return

        pos = e.position().toPoint()
        dx = pos.x() - self.last_mouse_pos.x()
        dy = pos.y() - self.last_mouse_pos.y()

        self.azimuth += dx * 0.5
        self.elevation = np.clip(self.elevation + dy * 0.5, -89, 89)

        self.last_mouse_pos = pos
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
        self.calculated_occlusion = []

    def showEvent(self, event):
        super().showEvent(event)
        if not self.calculated_occlusion:
            QTimer.singleShot(50, self.request_occlusion_test)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenGL Occlusion Debugger")
        self.gl = OcclusionGLWidget()

        btn = QPushButton("Run occlusion test")
        btn.clicked.connect(self.gl.request_occlusion_test)

        layout = QVBoxLayout(self)
        layout.addWidget(self.gl, 1)
        layout.addWidget(btn)

        self.gl.generate_test_data()


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(900, 700)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
