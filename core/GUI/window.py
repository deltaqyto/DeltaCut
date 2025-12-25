"""
Implementation using frameless window by ZhiYiYo @ https://github.com/zhiyiYo/PyQt-Frameless-Window
"""

import sys

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QShortcut, QKeySequence
# from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QApplication, QFileDialog, QMessageBox

from qframelesswindow import FramelessWindow

from core.GUI.frame import Frame
from core.GUI.main_menu import MainMenuBar
from core.GUI.titlebar import ApplicationTitleBar
from core.GUI.themes import ACTIVE_THEME
from core.application_state import ApplicationState
from core.export_engine import ExportEngine
from core.playback_engine import PlaybackEngine
from core.project.project import Project


class CrossPlatformWindow(FramelessWindow):
    """Utility window that implements cross-platform behaviours. Only draws a title bar"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setTitleBar(ApplicationTitleBar(self))

        self.label = QLabel(self)
        self.label.setScaledContents(True)
        # self.label.setPixmap(QPixmap("screenshot/shoko.png"))

        # self.setWindowIcon(QIcon("screenshot/logo.png"))
        # self.setWindowTitle("PyQt-Frameless-Window")
        self.setStyleSheet(f"background:{ACTIVE_THEME.background}")

        self.titleBar.raise_()

        # customize the area of system title bar button, only works for macOS
        if sys.platform == "darwin":
            self.setSystemTitleBarButtonVisible(True)
            self.titleBar.minBtn.hide()
            self.titleBar.maxBtn.hide()
            self.titleBar.closeBtn.hide()

    def resizeEvent(self, e):
        # don't forget to call the resizeEvent() of super class
        super().resizeEvent(e)
        length = min(self.width(), self.height())
        self.label.resize(length, length)
        self.label.move(
            self.width() // 2 - length // 2,
            self.height() // 2 - length // 2
        )

    def systemTitleBarRect(self, size: QSize) -> QRect:
        """ Returns the system title bar rect, only works for macOS

        Parameters
        ----------
        size: QSize
            original system title bar rect
        """
        return QRect(size.width() - 75, 0, 75, size.height())


class ApplicationWindow(CrossPlatformWindow):
    """The application window is the base window. Provides a top level frame and operating logic"""

    def __init__(self, parent, app: QApplication, project: Project):
        super().__init__(parent=parent)
        self.project: Project = project
        self.playback_engine: PlaybackEngine = PlaybackEngine(project.application_state, project.timeline)
        self.export_engine: ExportEngine = ExportEngine(project.application_state, project.timeline)
        self.app = app

        self.menu_bar = MainMenuBar(self.titleBar)
        self.titleBar.hBoxLayout.insertWidget(0, self.menu_bar, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setup_menu_bar_actions()

        self.frame = Frame(self, self.project)
        self.resize(800, 600)
        self.restore_default_window_layout()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(self.frame)

        self.project.render_current_frame_to_buffer()

    def toggle_playback(self):
        if self.playback_engine.is_playing or self.export_engine.is_exporting:
            self.playback_engine.stop()
        else:
            self.playback_engine.play(start_frame=self.project.application_state.current_playback_frame)

    def trigger_export(self):
        """Trigger export process for the entire timeline"""
        if self.export_engine.is_exporting:
            return

        self.playback_engine.stop()
        self.export_engine.start(start_frame=0)

    def set_application_state(self, application_state: ApplicationState):
        """Set application state to all sub items"""
        self.project.set_application_state(application_state)
        self.playback_engine.set_application_state(application_state)
        self.export_engine.set_application_state(application_state)

    def setup_menu_bar_actions(self):
        self.menu_bar.action_new_file.triggered.connect(self.create_new_timeline)
        self.menu_bar.action_open_file.triggered.connect(self.load_project)
        self.menu_bar.action_save_file.triggered.connect(self.save_project)

        self.menu_bar.action_export_project.triggered.connect(self.trigger_export)
        self.menu_bar.action_play.triggered.connect(self.toggle_playback)

        self.menu_bar.action_add_image.triggered.connect(lambda: self.add_timeline_object('ImageMediaTimelineObject'))
        self.menu_bar.action_add_audio.triggered.connect(lambda: self.add_timeline_object('AudioMediaTimelineObject'))

        self.menu_bar.action_reset_view.triggered.connect(self.restore_default_window_layout)

    def create_new_timeline(self):
        if self.project.application_state.is_timeline_locked:
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Save Current Project?")
        msg_box.setText("Do you want to save the current project?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
        msg_box.setStyleSheet(f"QLabel {{ color: {ACTIVE_THEME.on_background}; }}  QPushButton {{ color: {ACTIVE_THEME.on_background}; }}")
        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Save:
            if self.save_project():
                self.project.create_new_project()
        elif reply == QMessageBox.StandardButton.Discard:
            self.project.create_new_project()

    def load_project(self):
        if self.project.application_state.is_timeline_locked:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="Open Project",
            directory="",
            filter="Project Files (*.deltacut);;All Files (*)"
        )

        if file_path:
            self.project.load_from_file(file_path)

    def save_project(self) -> bool:
        """Trigger a project save. Return if the save was successful"""
        if self.project.application_state.is_timeline_locked:
            return False

        file_path, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Project",
            directory="",
            filter="Project Files (*.deltacut);;All Files (*)"
        )

        if file_path:
            self.project.save_to_file(file_path)
            return True

        return False

    def add_timeline_object(self, object_type):
        if self.project.application_state.is_timeline_locked:
            return

        valid_file_types = self.project.get_file_types_for_object_type(object_type)

        file_path: str | None = None
        if valid_file_types:
            file_filter = self._build_filter_string(valid_file_types)
            file_path, _ = QFileDialog.getOpenFileName(
                parent=self,
                caption="Select Media File",
                directory="",
                filter=file_filter
            )

        object_resource = None
        if file_path:
            object_resource = self.project.create_resource_from_file(file_path)

        self.project.create_timeline_object(object_type, object_resource=object_resource)

    @staticmethod
    def _build_filter_string(extensions: list[str]) -> str:
        """Convert extension list to QFileDialog filter string"""
        if not extensions:
            return "All Files (*)"

        extension_str = ' '.join(extensions)
        return f"Media Files ({extension_str});;All Files (*)"

    def restore_default_window_layout(self):
        window_layout = {'frame': {'is_bisected': True, 'vertical': True, 'division_ratio': 0.18375}, 'child_a': {'frame': {'is_bisected': False, 'vertical': False, 'division_ratio': 0.5}, 'child_a': None, 'child_b': None, 'panel_type': 'ErrorPanel'}, 'child_b': {'frame': {'is_bisected': True, 'vertical': False, 'division_ratio': 0.7288732394366197}, 'child_a': {'frame': {'is_bisected': False, 'vertical': False, 'division_ratio': 0.5}, 'child_a': None, 'child_b': None, 'panel_type': 'ViewportPanel'}, 'child_b': {'frame': {'is_bisected': False, 'vertical': False, 'division_ratio': 0.5}, 'child_a': None, 'child_b': None, 'panel_type': 'TimelinePanel'}, 'panel_type': None}, 'panel_type': None}
        self.frame.deserialise_layout(window_layout)
