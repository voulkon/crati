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
        # Remove parent from defaults - we'll handle it specially
        if 'parent' in defaults:
            parent_id = defaults.pop('parent')
            
            # Only try to set parent if it's not the same as the organization
            if 'organization' in defaults:
                org = defaults.get('organization')
                if org and org.uid != parent_id:
                    try:
                        parent_unit = Unit.objects.get(uid=parent_id)
                        defaults['parent'] = parent_unit
                    except Unit.DoesNotExist:
                        # Will be handled in the second pass
                        pass
        
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