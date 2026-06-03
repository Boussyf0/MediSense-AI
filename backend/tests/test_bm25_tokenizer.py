import pytest

from app.rag.bm25_tokenizer import (
    build_sparse_query,
    compute_sparse_vector,
    strip_accents,
    tokenize_for_bm25,
)


def test_strip_accents_removes_diacritics():
    assert strip_accents("céphalée") == "cephalee"


def test_tokenize_for_bm25_injects_bigrams_and_filters_stopwords():
    text = "Douleur thoracique et insuffisance cardiaque, céphalée intense."
    tokens = tokenize_for_bm25(text)

    assert "douleur" in tokens
    assert "thoracique" in tokens
    assert "insuffisance" in tokens
    assert "cardiaque" in tokens
    assert "cephalee" in tokens
    assert "intense" in tokens
    assert "douleur_thoracique" in tokens
    assert "insuffisance_cardiaque" in tokens
    assert "et" not in tokens


def test_compute_sparse_vector_counts_tokens():
    text = "douleur thoracique douleur thoracique"
    tokens = tokenize_for_bm25(text)
    indices, values = compute_sparse_vector(text)

    assert sum(values) == len(tokens)
    assert max(values) >= 2
    assert len(indices) == len(values)


def test_build_sparse_query_handles_empty_and_non_empty_inputs():
    assert build_sparse_query("de la et") is None

    vector = build_sparse_query("douleur thoracique")
    assert vector is not None
    assert len(vector.indices) == len(vector.values)
