import pytest
from unittest.mock import Mock, patch
from diavgeia_api.models.decisions import Decision as DecisionDTO
from diavgeia_api.models.organizations import (
    Unit as UnitDTO, 
    Organization as OrganizationDTO
    )
from core.importers.decisions import DecisionImporter
from core.models import Decision, Unit, Organization
from core.tests.utils import create_decision_dto

pytestmark = pytest.mark.django_db

def test_unit_organization_resolution_through_parent_chain():
    """
    Test the specific case where:
    - Decision has unit 100026211
    - Unit 100026211 has parentId 100026195 (no organizationId)
    - Unit 100026195 has organizationId 5009 (no parentId)
    - Both units should end up with organizationId 5009
    """
    
    # Mock the fetcher responses
    unit_100026211_dto = UnitDTO(
        uid="100026211",
        label="ΔΙΕΥΘΥΝΣΗ ΟΙΚΟΝΟΜΙΚΟΥ ( ΠΚΜ )",
        parentId="100026195",
        active = True,
        category = "ADMINISTRATION"
    )
    
    unit_100026195_dto = UnitDTO(
        uid="100026195", 
        label="ΓΕΝΙΚΗ ΔΙΕΥΘΥΝΣΗ ΕΣΩΤΕΡΙΚΗΣ ΟΡΓΑΝΩΣΗΣ ΚΑΙ ΛΕΙΤΟΥΡΓΙΑΣ",
        active = True,
        category = "ADMINISTRATION",
        parentId="100026195",
    )
    
    org_5009_dto = OrganizationDTO(
        uid="5009",
        label="ΠΕΡΙΦΕΡΕΙΑ ΚΕΝΤΡΙΚΗΣ ΜΑΚΕΔΟΝΙΑΣ",
        status="ACTIVE"
        )
    
    decision_dto = create_decision_dto(
        ada="9ΜΤΝ7ΛΛ-ΠΩΓ",
        org_id = "5009",
        # subject="Ανάγκες της Π.Ε Χαλκιδικής για τηλεπικοινωνίες",
        unitIds=["100026211"],
        signer_ids=["110954"],
        # status="PUBLISHED"
    )
    
    with patch('core.importers.decisions.DiavgeiaFetcher') as mock_fetcher_class:
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Configure fetcher responses
        def fetch_unit_side_effect(unit_id):
            if unit_id == "100026211":
                return unit_100026211_dto
            elif unit_id == "100026195":
                return unit_100026195_dto
            return None
            
        def fetch_org_side_effect(org_id):
            if org_id == "5009":
                return org_5009_dto
            return None
            
        mock_fetcher.fetch_a_unit.side_effect = fetch_unit_side_effect
        mock_fetcher.fetch_an_organization.side_effect = fetch_org_side_effect
        
        # Import the decision
        importer = DecisionImporter()
        created_count = importer.import_many([decision_dto])
        
        # Verify the decision was created
        assert created_count == 1
        decision = Decision.objects.get(ada="9ΜΤΝ7ΛΛ-ΠΩΓ")
        
        # Verify both units were created with the correct organization
        unit_211 = Unit.objects.get(uid="100026211")
        unit_195 = Unit.objects.get(uid="100026195")
        org = Organization.objects.get(uid="5009")
        
        # Both units should have the same organization
        assert unit_211.organization_id == "5009"
        assert unit_195.organization_id == "5009"
        
        # Unit 211 should have 195 as parent
        assert unit_211.parent_id == "100026195"
        
        # Unit 195 should have no parent (it's the top-level unit in this chain)
        assert unit_195.parent_id is None
        
        # Decision should be linked to the unit
        assert decision.units.filter(uid="100026211").exists()
