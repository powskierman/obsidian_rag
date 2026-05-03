from src.services.pdf_tree_extractor import clean_pdf_page_text


def test_clean_pdf_page_text_removes_common_page_artifacts():
    text = "Title\n\n\nPage 1 of 3\nA   B\tC"

    assert clean_pdf_page_text(text) == "Title\n\nA B C"
