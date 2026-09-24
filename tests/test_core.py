from pathlib import Path
import tempfile
from api.app.tools import SafeCalculator
from api.app.language import detect_script
from api.app.documents import extract_document
from api.app.db import Database
from api.app.rag import RAG

def test_calculator():
    c = SafeCalculator()
    assert c.evaluate("2 + 3 * 4") == 14
    assert round(c.evaluate("(437/512)*100"), 2) == 85.35
    assert c.evaluate("sqrt(144)") == 12

def test_calculator_blocks_code():
    try:
        SafeCalculator().evaluate("__import__('os').getcwd()")
    except ValueError:
        assert True
    else:
        assert False

def test_language():
    assert detect_script("Hello") == "English/Latin"
    assert detect_script("నమస్కారం") == "Telugu"
    assert detect_script("नमस्ते") == "Hindi"

def test_document():
    result = extract_document(b"machine learning " * 500, ".txt", "a.txt")
    assert result and all(x["content"] for x in result)

def test_rag():
    with tempfile.TemporaryDirectory() as d:
        db = Database(str(Path(d) / "x.db"))
        did = db.create_document("notes.txt", ".txt")
        db.insert_chunks(did, [
            {"page": 1, "section": "", "content": "Overfitting means memorizing training data."},
            {"page": 2, "section": "", "content": "Gradient descent updates parameters."}
        ])
        out = RAG(db, 2).search("overfitting training")
        assert out[0]["page"] == 1
