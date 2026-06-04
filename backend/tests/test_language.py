"""
Tests for language detection (FR / AR / Darija).

Covers:
  - French detection
  - Arabic MSA detection
  - Darija (Arabic script) detection
  - Darija Arabizi (Latin script) detection
  - Edge cases: empty, mixed, short
"""
from app.rag.language import detect_language, FRENCH, ARABIC, DARIJA


class TestFrenchDetection:
    def test_simple_french(self):
        assert detect_language("J'ai mal a la tete depuis trois jours") == FRENCH

    def test_medical_french(self):
        assert detect_language("Je ressens des douleurs thoraciques avec essoufflement") == FRENCH

    def test_french_with_numbers(self):
        assert detect_language("J'ai pris 2 comprimes de doliprane 500mg") == FRENCH

    def test_formal_french(self):
        assert detect_language("Bonjour docteur, je souhaite prendre rendez-vous") == FRENCH


class TestArabicDetection:
    def test_msa_arabic(self):
        assert detect_language("أعاني من صداع شديد منذ ثلاثة أيام") == ARABIC

    def test_medical_arabic(self):
        assert detect_language("لدي ألم في الصدر وصعوبة في التنفس") == ARABIC


class TestDarijaDetection:
    def test_darija_arabic_script(self):
        """Darija in Arabic script with dialectal markers."""
        assert detect_language("راسي كايديرني بزاف وكانشرب دوليبران") == DARIJA

    def test_darija_arabic_script_2(self):
        assert detect_language("واش كاين شي طبيب هنا ماشي بعيد") == DARIJA

    def test_darija_arabizi(self):
        """Darija in Latin script (Arabizi)."""
        assert detect_language("rasi kaydrni bzzaf w kanchrb doliprane") == DARIJA

    def test_darija_arabizi_2(self):
        assert detect_language("wach kayn chi tbib hna machi b3id") == DARIJA

    def test_darija_medical(self):
        assert detect_language("3andi douleur f sder w kanchouf chwiya ghbar f 3ini") == DARIJA

    def test_darija_with_french_words(self):
        """Darija often mixes with French medical terms."""
        assert detect_language("3andi mal de tete bzzaf w daba ghadi n3yet l docteur") == DARIJA


class TestEdgeCases:
    def test_empty_string(self):
        assert detect_language("") == FRENCH

    def test_whitespace(self):
        assert detect_language("   ") == FRENCH

    def test_single_word_french(self):
        assert detect_language("Bonjour") == FRENCH

    def test_numbers_only(self):
        """Pure numbers should default to French."""
        assert detect_language("12345") == FRENCH

    def test_mixed_short(self):
        """Short ambiguous text defaults to French."""
        assert detect_language("ok merci") == FRENCH
