from app.services.dpa_summarizer import _extract_symptom_phrases

def test_extract_symptom_phrases_duration():
    text = "J'ai mal à la tête depuis 5 minutes et je me sens très fatigué."
    phrases = _extract_symptom_phrases(text)
    assert len(phrases) == 1
    assert phrases[0]["name"] == "tête"
    assert phrases[0]["duration"] == "5 minutes"
    assert phrases[0]["severity"] == "moderate"

def test_extract_symptom_phrases_simple():
    text = "Je ressens des douleurs intenses au ventre."
    phrases = _extract_symptom_phrases(text)
    assert len(phrases) > 0
    # Match varies, but it shouldn't extract empty strings or stopwords
    names = [p["name"] for p in phrases]
    assert "douleurs intenses au ventre" in names or "douleurs intenses" in names or "ventre" in names

def test_extract_symptom_phrases_toux():
    text = "toux depuis 3 jours"
    phrases = _extract_symptom_phrases(text)
    assert len(phrases) == 1
    assert phrases[0]["name"] == "toux"
    assert phrases[0]["duration"] == "3 jours"

def test_extract_stopword_filter():
    text = "J'ai mal au" # Incomplete
    phrases = _extract_symptom_phrases(text)
    # Should not extract "au" as a symptom
    assert len(phrases) == 0
