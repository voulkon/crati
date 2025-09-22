from core.importers.base import BaseImporter
from core.models.organizations import Unit, UnitDomain
from core.models.field_mapping import field_map as imported_field_map
from django.db import transaction

class UnitImporter(BaseImporter):
    model = Unit
    field_map = imported_field_map["Unit"]
    
    def _to_defaults(self, dto):
        defaults = super()._to_defaults(dto)
        
        # Add resolution path if it exists
        if hasattr(dto, 'resolution_path'):
            defaults['resolution_path'] = dto.resolution_path

        # Store parent_id for later processing but don't set it now
        if 'parent' in defaults or 'parent_id' in defaults:
            # Store it as metadata for the second pass
            defaults['_deferred_parent_id'] = defaults.pop('parent', defaults.pop('parent_id', None))
    
        return defaults

class UnitDomainImporter(BaseImporter):
    model = UnitDomain
    field_map = imported_field_map.get("UnitDomain", {})
    
    @transaction.atomic
    def import_many(self, domain_strings, *, defaults=None):
        """Special implementation for domain strings instead of DTOs"""
        defaults = defaults or {}
        unit = defaults.get('unit')
        if not unit:
            raise ValueError("Unit must be provided in defaults")
            
        total = 0
        for domain in domain_strings:
            obj, created = self.model.objects.update_or_create(
                domain=domain,
                unit=unit,
                defaults=defaults
            )
            total += int(created)
        return total