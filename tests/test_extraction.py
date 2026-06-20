import extraction

def test_extract_text_nonempty(example_docx):
    text = extraction.extract_text(example_docx)
    assert isinstance(text, str)
    assert len(text.strip()) > 200            # the sample paper is substantial
    assert "EMBRAPII" in text.upper() or "embrapii" in text.lower()
