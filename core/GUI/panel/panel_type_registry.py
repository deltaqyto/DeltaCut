from core.GUI.panel.base_panel import ErrorPanel
from core.GUI.panel.timeline_panel import TimelinePanel
from core.GUI.panel.viewport_panel import ViewportPanel

DEFAULT_PANEL_TYPE = 'ViewportPanel'
PANEL_TYPE_REGISTRY = {'BasePanel': ErrorPanel, 'ErrorPanel': ErrorPanel, 'ViewportPanel': ViewportPanel,
                       'TimelinePanel': TimelinePanel}
