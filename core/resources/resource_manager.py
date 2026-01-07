import json

from core.resources.resources import BaseResource
from core.resources.resources_type_registry import RESOURCES_TYPE_REGISTRY


class ResourceManager:
    """Manages control and lifetime of all resources"""

    def __init__(self, serialised_data=None):
        self.resources: dict[str, BaseResource] = {}
        if serialised_data is not None:
            self.deserialise_resources(serialised_data)

    def add_resource(self, resource:BaseResource):
        """Register a resource with the manager"""
        self.resources[resource.resource_id] = resource

    def get_resource_by_resource_id(self, resource_id):
        """Return resource if it exists, or None"""
        return self.resources.get(resource_id)

    def serialise_resources(self):
        """Serialise the manager and metadata on all resources.
        Does not include the resource files themselves"""
        serialised_resources = {}
        for resource_id, resource in self.resources.items():
            serialised_resources[resource_id] = resource.serialise_resource()

        serialised_data = {'resource_manager': {},
                           'resources': serialised_resources}
        return serialised_data

    def deserialise_resources(self, serialised_data):
        """Deserialise the resources and manager from serialised format.
        Expects all resource files to be in the same place as they were"""
        self.resources = {}

        for resource_id, resource_data in serialised_data.get('resources', {}).items():
            resource_class = RESOURCES_TYPE_REGISTRY.get(resource_data['resource_type'])
            assert resource_class is not None, f'Unknown resource type: {resource_data["resource_type"]}'

            self.resources[resource_id] = resource_class(serialised_data=resource_data)

        # Resolve cross-resource references (eg transcript pointers
        for resource in self.resources.values():
            resource.resolve_references(self)

    def export_resource_files(self):
        """Allow all internally defined resource files to be exported for saving. Also saves a manifest"""
        resource_files: dict[str, bytes] = {}  # filename, resource data
        resource_manifest: dict[str, str] = {}

        for resource_id, resource in self.resources.items():
            if resource.uses_external_resource_file():
                continue
            filetype, data = resource.export_resource_file()

            assert resource_id + filetype not in resource_files, \
                (f"An internal resource file was about to be overwritten. This should never happen. "
                 f"resource: {resource_id}, filetype: {filetype}, resources: {resource_files.keys()}")
            
            resource_files[resource_id + filetype] = data
            resource_manifest[resource_id] = resource_id + filetype
        resource_files['resource_manifest.json'] = json.dumps(resource_manifest).encode()
        return resource_files

    def restore_resource_files(self, resource_files: dict[str, bytes]):
        """Restore resources to empty resources. Requires that all resource objects are already deserialised"""
        assert 'resource_manifest.json' in resource_files, f'Did not find resource manifest in resource files. Found: {resource_files.keys()}'
        resource_manifest: dict[str, str] = json.loads(resource_files['resource_manifest.json'].decode())

        for resource_id, resource in self.resources.items():
            if resource.uses_external_resource_file():
                continue
            resource_file = resource_files[resource_manifest[resource_id]]
            resource.import_resource_file(resource_file)
