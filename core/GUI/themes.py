"""Reading: https://m2.material.io/design/introduction"""

from dataclasses import dataclass

@dataclass
class ApplicationTheme:
    """Color palette for all visual elements"""

    name: str = "Carbon Amber"                                          
    background: str = "#0a0a0a"
    surface: str = "#303030"
    divider: str = "#151515"
    primary: str = "#c9904a"
    secondary: str = "#8a765a"
    error: str = "#ff471a" #"#d17a6f"

    on_background: str = "#e8e6e3"
    on_surface: str = "#e8e6e3"
    on_primary: str = "#ffffff"
    on_secondary: str = "#ffffff"
    on_error: str = "#ffffff"

    protected_menu_button: str = "#0a0a0a"
    protected_menu_button_hover: str = "#353535"
    protected_menu_button_text: str = "#e8e6e3"
    protected_menu_button_hint_text: str = "#c4c2be"

    protected_close_button: str = "#0a0a0a"
    protected_close_button_hover: str = "#cc0000"
    protected_close_button_press: str = "#990000"
    protected_close_button_text: str = "#ffffff"
    protected_resize_button: str = "#0a0a0a"
    protected_resize_button_hover: str = "#353535"
    protected_resize_button_press: str = "#454545"
    protected_resize_button_text: str = "#e8e6e3"

    selected_widget: str = "#ffcc66"

    object_video_ui: str = "#79b5ba"
    object_audio_ui: str = "#d5a6bc"
    object_shape_ui: str = "#c4a9a9"
    object_image_ui: str = "#a094bf"
    object_text_ui: str = "#ced5bc"

ACTIVE_THEME = ApplicationTheme()
