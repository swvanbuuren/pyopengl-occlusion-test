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

        self._setup_camera()
        self._draw_plane(alpha=0.35)
        self._draw_points()

    # ---------------- Camera ----------------

    def _setup_camera(self):
        w, h = self.width(), self.height()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GLU.gluPerspective(45.0, w / max(1, h), 0.1, 100.0)

        az, el = np.radians(self.azimuth), np.radians(self.elevation)
        cam_x = self.distance * np.cos(el) * np.sin(az)
        cam_y = self.distance * np.sin(el)
        cam_z = self.distance * np.cos(el) * np.cos(az)
        self.camera_pos = np.array([cam_x, cam_y, cam_z])

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GLU.gluLookAt(cam_x, cam_y, cam_z, *self.target, 0, 1, 0)

    # ---------------- Scene ----------------

    def _draw_plane(self, alpha=0.25):
        size = 1000.0
        y = self.plane_y

        # Depth-only pass
        GL.glDepthMask(True)
        GL.glColorMask(False, False, False, False)
        GL.glBegin(GL.GL_TRIANGLES)
        GL.glVertex3f(-size, y, -size)
        GL.glVertex3f(size, y, -size)
        GL.glVertex3f(size, y, size)
        GL.glVertex3f(-size, y, -size)
        GL.glVertex3f(size, y, size)
        GL.glVertex3f(-size, y, size)
        GL.glEnd()

        # Fill pass
        GL.glColorMask(True, True, True, True)
        GL.glDepthMask(False)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glColor4f(0.2, 0.6, 0.9, alpha)
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex3f(-size, y, -size)
        GL.glVertex3f(size, y, -size)
        GL.glVertex3f(size, y, size)
        GL.glVertex3f(-size, y, size)
        GL.glEnd()
        GL.glDisable(GL.GL_BLEND)
        GL.glDepthMask(True)

        # Wireframe
        GL.glColor3f(0.8, 0.8, 0.8)
        GL.glLineWidth(1.0)
        steps = 20
        step_size = size / steps
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

    # ---------------- Occlusion logic ----------------

    def run_occlusion_test(self):
        """Use OpenGL occlusion queries to check each point."""
        self.makeCurrent()
        self.calculated_occlusion.clear()

        # Prepare camera & depth buffer
        self._setup_camera()
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        self._draw_plane(alpha=0.35)

        # For each point, test if any pixel passes depth test
        for p in self.test_points:
            query = GL.glGenQueries(1)[0]
            GL.glBeginQuery(GL.GL_ANY_SAMPLES_PASSED, query)
            GL.glBegin(GL.GL_POINTS)
            GL.glVertex3f(*p)
            GL.glEnd()
            GL.glEndQuery(GL.GL_ANY_SAMPLES_PASSED)
            result = GL.glGetQueryObjectuiv(query, GL.GL_QUERY_RESULT)
            self.calculated_occlusion.append(not bool(result))
            GL.glDeleteQueries(1, [query])

        self.update()

    # ---------------- Input ----------------

    def mousePressEvent(self, e):
        self.last_mouse_pos = e.pos()

    def mouseMoveEvent(self, e):
        if self.last_mouse_pos is None:
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
        self.calculated_occlusion = [False] * n

    def showEvent(self, event):
        super().showEvent(event)
        if not any(self.calculated_occlusion):
            QTimer.singleShot(50, self.run_occlusion_test)


# ---------------- Main Window ----------------

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenGL Occlusion Debugger")
        self.gl = OcclusionGLWidget()

        btn = QPushButton("Run occlusion test")
        btn.clicked.connect(self.gl.run_occlusion_test)

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
