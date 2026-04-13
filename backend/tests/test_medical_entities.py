"""
Tests for medical entity extraction.

Covers:
  - ICD-10 code mapping from symptoms
  - Drug name extraction
  - Urgency detection
  - Multiple entities in one query
  - No matches
"""
import pytest
from app.rag.medical_entities import extract_entities


class TestICD10Extraction:
    def test_headache_maps_to_r51(self):
        result = extract_entities("cephalee severe depuis 3 jours")
        assert "R51" in result.icd10_codes
        assert "cephalee" in result.matched_symptoms

    def test_chest_pain_maps_to_cardiac(self):
        result = extract_entities("douleur thoracique intense irradiant vers le bras")
        assert "I20" in result.icd10_codes or "I21" in result.icd10_codes

    def test_fever_maps_to_r50(self):
        result = extract_entities("fievre elevee depuis 2 jours")
        assert "R50" in result.icd10_codes

    def test_multiple_symptoms(self):
        result = extract_entities("fievre avec toux et fatigue")
        assert "R50" in result.icd10_codes
        assert "R05" in result.icd10_codes
        assert "R53" in result.icd10_codes

    def test_no_symptoms(self):
        result = extract_entities("bonjour je voudrais prendre rendez-vous")
        assert result.icd10_codes == []


class TestDrugExtraction:
    def test_paracetamol(self):
        result = extract_entities("j'ai pris du paracetamol ce matin")
        assert "paracetamol" in result.drug_names

    def test_doliprane(self):
        result = extract_entities("je prends du doliprane 1000")
        assert "doliprane" in result.drug_names

    def test_multiple_drugs(self):
        result = extract_entities("je prends ibuprofene et omeprazole")
        assert "ibuprofene" in result.drug_names
        assert "omeprazole" in result.drug_names

    def test_no_drugs(self):
        result = extract_entities("j'ai mal a la tete")
        assert result.drug_names == []


class TestUrgencyDetection:
    def test_chest_pain_is_urgent(self):
        result = extract_entities("douleur thoracique intense depuis 30 minutes")
        assert result.is_urgent is True

    def test_difficulty_breathing_is_urgent(self):
        result = extract_entities("difficulte respiratoire soudaine")
        assert result.is_urgent is True

    def test_loss_of_consciousness_is_urgent(self):
        result = extract_entities("perte de connaissance brutale")
        assert result.is_urgent is True

    def test_headache_not_urgent(self):
        result = extract_entities("cephalee moderee depuis une semaine")
        assert result.is_urgent is False

    def test_general_query_not_urgent(self):
        result = extract_entities("je voudrais renouveler mon ordonnance")
        assert result.is_urgent is False
