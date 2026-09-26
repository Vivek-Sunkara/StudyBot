from pathlib import Path
import tempfile
from api.app.tools import SafeCalculator, execute_tool
from api.app.language import detect_script
from api.app.documents import extract_document
from api.app.db import Database
from api.app.rag import RAG
from api.app.routing import calculator_expression, classify_query, retrieval_query, requests_document_summary
from api.app.llm import SYSTEM

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

def test_rag_fallback_answers_with_relevant_sentences_only():
    with tempfile.TemporaryDirectory() as d:
        db = Database(str(Path(d) / "focused.db"))
        did = db.create_document("notes.txt", ".txt")
        db.insert_chunks(did, [{
            "page": 1,
            "section": "",
            "content": "Overfitting means memorizing training data. "
                       "Gradient descent updates parameters. "
                       "Regularization can reduce overfitting."
        }])
        rag = RAG(db, 2)
        answer = rag.fallback("What is overfitting?", rag.search("What is overfitting?"), "English/Latin")
        assert "Overfitting means memorizing training data." in answer
        assert "Gradient descent updates parameters." not in answer

def test_llm_synthesizes_instead_of_copying_document_chunks():
    assert "answer it directly in your own words" in SYSTEM
    assert "returning whole chunks" in SYSTEM
    assert "proofread the complete answer" in SYSTEM

def test_query_routing():
    assert classify_query("Hi") == "conversation"
    assert classify_query("How are you?") == "conversation"
    assert classify_query("నమస్కారం") == "conversation"
    assert classify_query("What is photosynthesis?") == "general"
    assert classify_query("Explain this in detail") == "explanation"
    assert classify_query("What does the document say about overfitting?") == "document"
    assert classify_query("Calculate (437/512)*100") == "calculator"

def test_document_summary_retrieves_indexed_chunks_without_keyword_overlap():
    assert requests_document_summary("Can you summarize the document?")
    with tempfile.TemporaryDirectory() as d:
        db = Database(str(Path(d) / "summary.db"))
        did = db.create_document("notes.txt", ".txt")
        db.insert_chunks(did, [{"page": 1, "section": "", "content": "Gradient descent updates model parameters."}])
        results = RAG(db).search("Can you summarize the document?", include_all=True)
        assert len(results) == 1
        assert "Gradient descent" in results[0]["content"]

def test_follow_up_uses_previous_topic_for_retrieval():
    history = [{"role": "user", "content": "What is overfitting?"}]
    assert classify_query("Explain it more", True) == "explanation"
    assert retrieval_query("Explain it more", history, "explanation") == \
        "What is overfitting?\nExplain it more"

def test_missing_document_information_remains_unavailable():
    with tempfile.TemporaryDirectory() as d:
        db = Database(str(Path(d) / "empty.db"))
        answer = RAG(db).fallback("What is absent?", [], "English/Latin")
        assert "could not find sufficiently relevant information" in answer

def test_calculator_request_uses_safe_calculator():
    expression = calculator_expression("Calculate (437/512)*100")
    assert round(float(execute_tool("calculate", {"expression": expression})), 2) == 85.35

def test_database_conversation_history():
    with tempfile.TemporaryDirectory() as d:
        db = Database(str(Path(d) / "history.db"))
        db.add_message("c1", "user", "What is overfitting?")
        db.add_message("c1", "assistant", "It is memorization of training data.")
        assert db.get_messages("c1") == [
            {"role": "user", "content": "What is overfitting?"},
            {"role": "assistant", "content": "It is memorization of training data."},
        ]
