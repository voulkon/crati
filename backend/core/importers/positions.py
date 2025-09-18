from core.models.organizations import Position
from core.models.field_mapping import field_map as imported_field_map
from core.importers.base import BaseImporter

class PositionImporter(BaseImporter):
    model = Position
    field_map = imported_field_map.get("Position", {})
