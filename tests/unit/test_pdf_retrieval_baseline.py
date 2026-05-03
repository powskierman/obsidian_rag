import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "Scripts" / "benchmarks" / "run_pdf_retrieval_baseline.py"
SPEC = importlib.util.spec_from_file_location("run_pdf_retrieval_baseline", SCRIPT_PATH)
baseline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(baseline)


def test_page_hit_uses_structured_pdf_tree_page_ranges():
    result = {
        "sources": [
            {"filepath": "manual.pdf", "page_start": 10, "page_end": 13},
        ],
    }

    assert baseline.page_hit(12, result) is True
    assert baseline.page_hit(14, result) is False


def test_post_query_routes_pdf_tree_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return b'{"sources":[]}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["json"] = baseline.json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(baseline.request, "urlopen", fake_urlopen)

    result, elapsed = baseline.post_query(
        "http://gateway",
        {
            "query": "Find section in the PDF",
            "expected_source": "Docs/manual.pdf",
            "pdf_tree_provider": "lmstudio",
            "pdf_tree_model": "local-model",
        },
        30,
        mode="pdf-tree",
    )

    assert result == {"sources": []}
    assert elapsed >= 0
    assert captured["url"] == "http://gateway/api/v1/pdf-tree/query"
    assert captured["json"]["candidate_paths"] == ["Docs/manual.pdf"]
    assert captured["json"]["provider"] == "lmstudio"
    assert captured["json"]["model"] == "local-model"


def test_post_query_routes_hybrid_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return b'{"sources":[]}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["json"] = baseline.json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(baseline.request, "urlopen", fake_urlopen)

    baseline.post_query(
        "http://gateway/",
        {"query": "Find page", "candidate_paths": ["Docs/file.pdf"]},
        30,
        mode="hybrid",
    )

    assert captured["url"] == "http://gateway/api/v1/query"
    assert captured["json"]["pdf_tree_enabled"] is True
    assert captured["json"]["pdf_tree_candidate_paths"] == ["Docs/file.pdf"]
