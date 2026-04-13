"""
Tests for the medical safety layer.

Covers:
  - Urgency detection and override
  - Low confidence blocking
  - Drug dosage warning injection
  - Post-generation dosage scanning
  - Standard disclaimer appending
"""
import pytest
from app.rag.safety import (
    pre_generation_check,
    post_generation_check,
    URGENCY_MESSAGE,
    LOW_CONFIDENCE_MESSAGE,
    DOSAGE_DISCLAIMER,
    STANDARD_DISCLAIMER,
    CONFIDENCE_THRESHOLD,
)
from app.rag.medical_entities import ExtractedEntities


def _make_entities(
    icd10_codes=None,
    drug_names=None,
    is_urgent=False,
    matched_symptoms=None,
) -> ExtractedEntities:
    return ExtractedEntities(
        icd10_codes=icd10_codes or [],
        drug_names=drug_names or [],
        is_urgent=is_urgent,
        matched_symptoms=matched_symptoms or [],
    )


class TestPreGenerationCheck:
    def test_urgency_blocks_generation(self):
        entities = _make_entities(is_urgent=True)
        result = pre_generation_check(entities, [0.8, 0.7])
        assert result.should_block is True
        assert result.is_urgent is True
        assert result.override_response == URGENCY_MESSAGE

    def test_low_confidence_blocks_generation(self):
        entities = _make_entities()
        result = pre_generation_check(entities, [0.1, 0.2])
        assert result.should_block is True
        assert result.override_response == LOW_CONFIDENCE_MESSAGE

    def test_empty_scores_blocks(self):
        entities = _make_entities()
        result = pre_generation_check(entities, [])
        assert result.should_block is True

    def test_sufficient_confidence_passes(self):
        entities = _make_entities()
        result = pre_generation_check(entities, [0.5, 0.6])
        assert result.should_block is False
        assert result.override_response is None

    def test_drug_adds_dosage_disclaimer(self):
        entities = _make_entities(drug_names=["paracetamol"])
        result = pre_generation_check(entities, [0.5, 0.6])
        assert result.should_block is False
        assert DOSAGE_DISCLAIMER in result.disclaimers

    def test_no_drug_no_dosage_disclaimer(self):
        entities = _make_entities()
        result = pre_generation_check(entities, [0.5, 0.6])
        assert DOSAGE_DISCLAIMER not in result.disclaimers
        assert STANDARD_DISCLAIMER in result.disclaimers


class TestPostGenerationCheck:
    def test_appends_standard_disclaimer(self):
        result = post_generation_check("Some response", [STANDARD_DISCLAIMER])
        assert STANDARD_DISCLAIMER in result

    def test_detects_dosage_in_response(self):
        response = "Prenez 500mg de paracetamol toutes les 6 heures"
        result = post_generation_check(response, [STANDARD_DISCLAIMER])
        assert DOSAGE_DISCLAIMER in result

    def test_no_duplicate_disclaimers(self):
        response = "Prenez 500mg de paracetamol"
        disclaimers = [STANDARD_DISCLAIMER, DOSAGE_DISCLAIMER]
        result = post_generation_check(response, disclaimers)
        assert result.count(DOSAGE_DISCLAIMER) == 1

    def test_clean_response_no_extra_disclaimers(self):
        response = "Vous devriez consulter votre medecin"
        result = post_generation_check(response, [STANDARD_DISCLAIMER])
        assert DOSAGE_DISCLAIMER not in result
        assert STANDARD_DISCLAIMER in result
