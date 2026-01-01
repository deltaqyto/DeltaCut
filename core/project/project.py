import json
import zipfile
import io

from core.application_state import ApplicationState
from core.resources.resources import BaseResource
from core.resources.resources_type_registry import RESOURCES_FILE_TYPE_REGISTRY, get_resource_type_from_file_type, RESOURCES_TYPE_REGISTRY
from core.timeline import Timeline
from core.resources.resource_manager import ResourceManager
from core.timeline_objects.timeline_objects_type_registry import TIMELINE_OBJECT_RESOURCE_TYPE_REGISTRY, TIMELINE_OBJECT_TYPE_REGISTRY


class Project:
    """
    Manages project data including timeline, resources, and project settings.

    Handles serialisation/deserialisation and file I/O operations. Projects are
    saved as ZIP archives containing a project.json file with all serialised data.
    """

    def __init__(self, application_state: ApplicationState):
        """
        Initialise a new project.
        """
        self.resource_manager = ResourceManager()
        self.application_state: ApplicationState = application_state
        self.application_state.resource_manager = self.resource_manager
        self.timeline: Timeline = Timeline(application_state)

    def serialise(self):
        """
        Serialise the entire project state to a dictionary.
        """
        return {
            'timeline': self.timeline.serialise_timeline(),
            'resources': self.application_state.resource_manager.serialise_resources(),
            'project_settings': self.application_state.project_settings.serialise()
        }

    def deserialise(self, serialised_data):
        """
        Restore project state from serialised data.
        """
        self.application_state.project_settings.deserialise(serialised_data.get('project_settings'))
        self.application_state.resource_manager.deserialise_resources(serialised_data.get('resources'))
        self.timeline = Timeline(self.application_state, serialised_data=serialised_data.get('timeline'))

    def create_new_project(self):
        """Reset to a new project"""
        self.timeline = Timeline(self.application_state)
        self.application_state.signal_timeline_content_update.emit()
        self.render_current_frame_to_buffer()

    def save_to_file(self, filename):
        """
        Save the project to a ZIP archive file.

        Creates a ZIP archive containing project.json with all serialised project data.
        The archive is constructed in memory and written to disk.

        Args:
            filename: Path where the project ZIP file should be saved.
        """
        serialised_data = self.serialise()
        json_content = json.dumps(serialised_data, indent=2)
        resource_files = self.application_state.resource_manager.export_resource_files()

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('project.json', json_content)
            for resource_name, file_data in resource_files.items():
                zip_file.writestr(f'resources/{resource_name}', file_data)

        with open(filename, 'wb') as f:
            f.write(buffer.getvalue())

    def load_from_file(self, filename):
        """
        Load a project from a ZIP archive file.

        Reads the ZIP archive and deserialises the project data.

        Args:
            filename: Path to the project ZIP file to load.
        """
        BaseResource.clear_all_registries()
        self.resource_manager = ResourceManager()
        self.application_state.resource_manager = self.resource_manager
        with zipfile.ZipFile(filename, 'r') as zip_file:
            json_content = zip_file.read('project.json').decode('utf-8')
            serialised_data = json.loads(json_content)
            self.deserialise(serialised_data)

            resource_files = {}
            for file_path in zip_file.namelist():
                if file_path.startswith('resources/'):
                    resource_name = file_path[len('resources/'):]
                    resource_files[resource_name] = zip_file.read(file_path)

        self.application_state.resource_manager.restore_resource_files(resource_files)
        self.render_current_frame_to_buffer()

    def set_application_state(self, application_state: ApplicationState):
        """Set application state to all sub items"""
        self.application_state = application_state
        self.application_state.resource_manager = self.resource_manager
        self.timeline.set_application_state(application_state)

    @staticmethod
    def get_file_types_for_object_type(object_type):
        """Wrapper to look up valid file types for a given timeline object's resource"""
        resource_types = TIMELINE_OBJECT_RESOURCE_TYPE_REGISTRY.get(object_type, [])
        file_types = []
        for resource in resource_types:
            file_types += RESOURCES_FILE_TYPE_REGISTRY.get(resource, [])
        return file_types

    def create_timeline_object(self, object_type, start_frame=None, object_resource=None):
        if start_frame is None:
            start_frame = self.application_state.current_playback_frame

        timeline_object_class = TIMELINE_OBJECT_TYPE_REGISTRY.get(object_type)
        assert timeline_object_class is not None, f"Project: Object type is not recognised: {object_type}"
        timeline_object = timeline_object_class(self.application_state, object_resource=object_resource)

        valid_channel = 0
        while self.timeline.check_collision(start_frame, start_frame + timeline_object.duration, valid_channel):
            valid_channel += 1

        self.timeline.add_entry(start_frame, valid_channel, timeline_object)
        self.application_state.signal_timeline_content_update.emit()

    def create_resource_from_file(self, file_path: str, resource_type: str | None=None):
        """
        Create a resource object from a file.
        Resource type is inferred from extension, or from override
        """
        if resource_type is None:
            resource_type = get_resource_type_from_file_type('*.' + file_path.split('.')[-1])
        assert resource_type is not None, f"Project: Resource type cannot be determined from path: {file_path}"

        resource_class = RESOURCES_TYPE_REGISTRY.get(resource_type)
        assert resource_class is not None, f"Project: Resource class cannot be found: {resource_type}"

        resource_instance = resource_class(path=file_path)
        self.application_state.resource_manager.add_resource(resource_instance)
        return resource_instance

    def render_current_frame_to_buffer(self):
        """Wrapper for render_frame that automatically writes result to framebuffer and signals appropriate sources"""
        self.application_state.rendered_frame.visual_frame = self.timeline.render_frame(self.application_state.current_playback_frame)
        self.application_state.signal_frame_buffer_update.emit()
