#!/usr/bin/env python3
import sys
import numpy as np
from OpenGL import GL, GLU

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt


class OcclusionGLWidget(QOpenGLWidget):
    def __init__(self):
        super().__init__()

        self.plane_y = None
        self.test_points = []
        self.expected_occlusion = []
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

        self._draw_plane(alpha=0.35)
        self._draw_points()

    # ---------------- Camera ----------------

    def _setup_matrices(self):
        w, h = self.width(), self.height()
        aspect = w / max(1, h)

        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GLU.gluPerspective(45.0, aspect, 0.1, 100.0)

        # spherical → cartesian
        az = np.radians(self.azimuth)
        el = np.radians(self.elevation)

        cam_x = self.distance * np.cos(el) * np.sin(az)
        cam_y = self.distance * np.sin(el)
        cam_z = self.distance * np.cos(el) * np.cos(az)

        self.camera_pos = np.array([cam_x, cam_y, cam_z])

        self.update_camera_position()

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GLU.gluLookAt(
            cam_x, cam_y, cam_z,
            *self.target,
            0, 1, 0
        )

    # ---------------- Scene ----------------

    def _draw_plane(self, alpha=0.25):
        """Draw the plane with a translucent fill and a visible light grey wireframe."""
        size = 1000.0
        y = self.plane_y

        GL.glDisable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_DEPTH_TEST)

        # --------------------------------------------------
        # 1) DEPTH-ONLY PASS (for occlusion)
        # --------------------------------------------------
        GL.glDepthMask(GL.GL_TRUE)
        GL.glColorMask(False, False, False, False)

        GL.glBegin(GL.GL_TRIANGLES)
        GL.glVertex3f(-size, y, -size)
        GL.glVertex3f( size, y, -size)
        GL.glVertex3f( size, y,  size)

        GL.glVertex3f(-size, y, -size)
        GL.glVertex3f( size, y,  size)
        GL.glVertex3f(-size, y,  size)
        GL.glEnd()

        # --------------------------------------------------
        # 2) Fill Pass (translucent)
        # --------------------------------------------------
        GL.glColorMask(True, True, True, True)
        GL.glDepthMask(False)  # do NOT modify depth

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

        # --------------------------------------------------
        # 3) Wireframe overlay (light grey)
        # --------------------------------------------------
        GL.glColor3f(0.8, 0.8, 0.8)  # light grey grid lines
        GL.glLineWidth(1.0)

        steps = 20
        step_size = size / steps

        GL.glBegin(GL.GL_LINES)
        for i in range(-steps, steps + 1):
            x = i * step_size
            GL.glVertex3f(x, y, -size)
            GL.glVertex3f(x, y,  size)

            z = i * step_size
            GL.glVertex3f(-size, y, z)
            GL.glVertex3f( size, y, z)
        GL.glEnd()

        # Re-enable depth writes for other objects
        GL.glDepthMask(True)

    def _draw_points(self):
        GL.glPointSize(8.0)
        GL.glBegin(GL.GL_POINTS)

        for p, occ in zip(self.test_points, self.calculated_occlusion):
            if occ:
                GL.glColor3f(1.0, 0.2, 0.2)
            else:
                GL.glColor3f(0.2, 1.0, 0.2)
            GL.glVertex3f(*p)

        GL.glEnd()

    # ---------------- Occlusion logic ----------------

    def run_occlusion_test(self):
        self.makeCurrent()
        self.calculated_occlusion.clear()

        modelview = GL.glGetDoublev(GL.GL_MODELVIEW_MATRIX)
        projection = GL.glGetDoublev(GL.GL_PROJECTION_MATRIX)
        viewport = GL.glGetIntegerv(GL.GL_VIEWPORT)

        for point in self.test_points:
            winx, winy, winz = GLU.gluProject(
                *point, modelview, projection, viewport
            )

            x, y, w, h = viewport
            px, py = int(winx), int(winy)

            if not (x <= px < x + w and y <= py < y + h):
                self.calculated_occlusion.append(True)
                continue

            GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
            depth = GL.glReadPixels(
                px, py, 1, 1,
                GL.GL_DEPTH_COMPONENT,
                GL.GL_FLOAT
            )

            self.calculated_occlusion.append(depth[0][0] < winz - 1e-6)

        self.update()

    # ---------------- Input ----------------

    def mousePressEvent(self, e):
        self.last_mouse_pos = e.pos()

    def mouseMoveEvent(self, e):
        if self.last_mouse_pos is None:
            return

        dx = e.x() - self.last_mouse_pos.x()
        dy = e.y() - self.last_mouse_pos.y()

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
        self.update_camera_position()

        np.random.seed(42)
        self.plane_y = np.random.uniform(-2, 2)

        self.test_points.clear()
        self.expected_occlusion.clear()

        for _ in range(n):
            p = np.random.uniform(-5, 5, 3)
            self.test_points.append(p)

            ray = p - self.camera_pos
            if abs(ray[1]) < 1e-6:
                self.expected_occlusion.append(False)
            else:
                t = (self.plane_y - self.camera_pos[1]) / ray[1]
                self.expected_occlusion.append(0 < t < 1)


    def update_camera_position(self):
        az = np.radians(self.azimuth)
        el = np.radians(self.elevation)

        cam_x = self.distance * np.cos(el) * np.sin(az)
        cam_y = self.distance * np.sin(el)
        cam_z = self.distance * np.cos(el) * np.cos(az)

        self.camera_pos = np.array([cam_x, cam_y, cam_z])


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
