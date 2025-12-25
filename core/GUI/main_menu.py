from PyQt6.QtGui import QAction

from core.GUI.menu_bar.menu_bar import MenuBar


class MainMenuBar(MenuBar):
    """Main menu bar for use in the main application window"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # File menu
        file_menu = self.addMenu('File')

        self.action_new_file = QAction('New', self)
        self.action_new_file.setShortcut('Ctrl+N')
        file_menu.addAction(self.action_new_file)

        self.action_open_file = QAction('Open', self)
        self.action_open_file.setShortcut('Ctrl+O')
        file_menu.addAction(self.action_open_file)

        self.action_save_file = QAction('Save', self)
        self.action_save_file.setShortcut('Ctrl+S')
        file_menu.addAction(self.action_save_file)
        # TODO app settings panel

        # Project menu
        project_menu = self.addMenu('Project')

        self.action_play = QAction('Play', self)
        self.action_play.setShortcut('Space')
        project_menu.addAction(self.action_play)
        self.action_export_project = QAction('Export', self)
        self.action_export_project.setShortcut('Ctrl+E')
        project_menu.addAction(self.action_export_project)
        # TODO export config panel

        # Add menu
        add_menu = self.addMenu('Add')

        self.action_add_image = QAction('Image', self)
        add_menu.addAction(self.action_add_image)

        self.action_add_audio = QAction('Audio', self)
        add_menu.addAction(self.action_add_audio)

        # View menu
        view_menu = self.addMenu('View')

        self.action_reset_view = QAction('Reset View', self)
        view_menu.addAction(self.action_reset_view)
