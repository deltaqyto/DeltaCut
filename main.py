import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from core.GUI.window import ApplicationWindow
from core.application_state import ApplicationState
from core.project.project import Project

# Temp includes
from core.resources.audio_resource import AudioResource
from core.resources.image_resource import ImageResource
from core.timeline_objects.media_timeline_object import AudioMediaTimelineObject
from core.timeline_objects.image_media_timeline_object import ImageMediaTimelineObject


def main():
    app = QApplication([])
    application_state = ApplicationState()

    # Temporarily hardcode the default layout
    audio_resource_1 = AudioResource(str(Path("testing_resources") / "test01_20s.wav"))
    image_resource_1 = ImageResource(str(Path(r"testing_resources") / "river_rock.jpg"))
    image_resource_2 = ImageResource(str(Path(r"testing_resources") / "cheetahs_ahmed_galal.jpg"))

    application_state.resource_manager.add_resource(audio_resource_1)
    application_state.resource_manager.add_resource(image_resource_1)
    application_state.resource_manager.add_resource(image_resource_2)

    # Temporarily hardcode export settings
    application_state.project_settings.export_container.file_path = str(Path("debug") / "output")
    application_state.project_settings.export_container.export_audio.set_value(False)
    application_state.project_settings.export_codec.audio_codec.set_value('mp3')

    project = Project(application_state)

    audio_1 = AudioMediaTimelineObject(application_state, 'Demo Speech', None, audio_resource_1, duration=-1)
    audio_1.attempt_change_object_duration(desired_start_offset=200)
    project.timeline.add_entry(0, 0, audio_1)
    project.timeline.add_entry(0, 2, ImageMediaTimelineObject(application_state, 'River', None, image_resource_1, 200))
    project.timeline.add_entry(200, 2, ImageMediaTimelineObject(application_state, 'Cheetah', None, image_resource_2, 100))

    project2 = Project(ApplicationState())
    project_serial = project.serialise()
    project2.deserialise(project_serial)
    project2_serial = project2.serialise()
    assert project_serial == project2_serial

    project2.set_application_state(application_state)  # Application state must be persisted between reserialisation
    window = ApplicationWindow(None, app, project2)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
