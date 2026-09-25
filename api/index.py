import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.app.config import settings
from api.app.db import Database
from api.app.documents import extract_document
from api.app.images import analyze_image_bytes
from api.app.language import detect_script
from api.app.rag import RAG
from api.app.routing import calculator_expression, classify_query, retrieval_query
from api.app.tools import execute_tool, TOOL_SCHEMAS
from api.app.llm import LLM

app = FastAPI(title="StudyRAG API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"]
)

db = Database(settings.database_path)
rag = RAG(db, settings.top_k)
llm = LLM()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: Optional[str] = None

@app.get("/api/health")
def health():
    return {"ok": True, "groq_configured": llm.enabled,
            "documents": db.document_count(), "chunks": db.chunk_count()}

@app.get("/api/documents")
def documents():
    return db.list_documents()

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(400, "Supported files: PDF, DOCX, TXT, MD")
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    try:
        chunks = extract_document(data, suffix, file.filename or "document")
        if not chunks:
            raise ValueError("No readable text found")
        doc_id = db.create_document(file.filename or "document", suffix)
        db.insert_chunks(doc_id, chunks)
        rag.invalidate()
        return {"ok": True, "document_id": doc_id, "chunks": len(chunks)}
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post("/api/chat")
def chat(req: ChatRequest):
    lang = detect_script(req.message)
    history = db.get_messages(req.conversation_id) if req.conversation_id else []
    route = classify_query(req.message, bool(history))
    results = rag.search(retrieval_query(req.message, history, route)) \
        if route not in {"conversation", "calculator"} else []
    if llm.enabled:
        try:
            answer, calls = llm.answer(
                req.message, lang, results, execute_tool, TOOL_SCHEMAS,
                history=history, route=route,
            )
            mode = "groq+local-rag"
        except Exception:
            if route == "conversation":
                answer = "Hello! I can help you study, explain concepts, and work with your uploaded notes."
            elif route == "calculator":
                answer = "I could not complete the calculation safely."
            else:
                answer = rag.fallback(req.message, results, lang)
            calls = []
            mode = "local-rag-fallback"
    else:
        if route == "calculator":
            answer, calls = "Calculator requests require a configured language model.", []
        elif route == "conversation":
            answer, calls = "Hello! I can help you study, explain concepts, and work with your uploaded notes.", []
        elif route in {"document", "explanation"}:
            answer, calls = rag.fallback(req.message, results, lang), []
        else:
            answer, calls = rag.fallback(req.message, results, lang), []
        mode = "local-rag"
    if req.conversation_id:
        db.add_message(req.conversation_id, "user", req.message)
        db.add_message(req.conversation_id, "assistant", answer)
    return {
        "answer": answer, "language": lang, "mode": mode, "tool_calls": calls,
        "sources": [
            {"document": x["document"], "page": x["page"],
             "score": round(float(x["score"]), 4), "chunk_id": x["chunk_id"]}
            for x in results
        ]
    }

@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    try:
        return analyze_image_bytes(data)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post("/api/analyze-video")
async def analyze_video(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    suffix = Path(file.filename or "").suffix.lower() or ".mp4"
    temp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(data)
            temp = f.name
        from api.app.video import analyze_video_file
        return analyze_video_file(temp)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        if temp:
            try: os.unlink(temp)
            except OSError: pass
