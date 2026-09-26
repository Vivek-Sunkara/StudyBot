import os
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.app.config import settings
from api.app.db import Database, MongoDatabase
from api.app.documents import extract_document
from api.app.images import analyze_image_bytes
from api.app.language import detect_script
from api.app.rag import RAG
from api.app.routing import calculator_expression, classify_query, retrieval_query, requests_document_summary, requested_media_kind
from api.app.tools import execute_tool, TOOL_SCHEMAS
from api.app.llm import LLM

logger = logging.getLogger(__name__)

app = FastAPI(title="StudyRAG API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"]
)

db = MongoDatabase(settings.mongodb_uri, settings.mongodb_database) if settings.mongodb_uri else Database(settings.database_path)
rag = RAG(db, settings.top_k)
llm = LLM()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: Optional[str] = None

class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)

@app.get("/api/health")
def health():
    return {"ok": True, "groq_configured": llm.enabled,
            "documents": db.document_count(), "chunks": db.chunk_count()}

@app.get("/api/documents")
def documents():
    return db.list_documents()

@app.get("/api/library")
def library():
    return db.list_documents()

@app.patch("/api/library/{document_id}")
def rename_library_item(document_id: str, req: RenameRequest):
    try:
        name = req.name.strip()
        if not name or not db.rename_document(document_id, name):
            raise HTTPException(404, "Library item not found")
        rag.invalidate()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(404, "Library item not found") from exc

@app.delete("/api/library/{document_id}")
def delete_library_item(document_id: str):
    try:
        db.delete_document(document_id)
        rag.invalidate()
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(404, "Library item not found") from exc

@app.get("/api/chats")
def chats():
    return db.list_conversations()

@app.get("/api/chats/{conversation_id}")
def chat_history(conversation_id: str):
    return {"id": conversation_id, "messages": db.get_messages(conversation_id, limit=1000)}

@app.patch("/api/chats/{conversation_id}")
def rename_chat(conversation_id: str, req: RenameRequest):
    name = req.name.strip()
    if not name or not db.rename_conversation(conversation_id, name):
        raise HTTPException(404, "Chat not found")
    return {"ok": True}

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
        doc_id = db.create_document(file.filename or "document", suffix, "document", data)
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
    media_kind = requested_media_kind(req.message)
    results = rag.search(retrieval_query(req.message, history, route),
                         include_all=requests_document_summary(req.message),
                         kinds={media_kind} if media_kind else None) \
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
        analysis = analyze_image_bytes(data)
        description = None
        vision_error = None
        if llm.enabled:
            try:
                description = llm.describe_image(data, file.content_type or "image/jpeg")
            except Exception as exc:
                vision_error = type(exc).__name__
                logger.exception("Image description request failed")
            if description:
                doc_id = db.create_document(file.filename or "image", ".image", "image", data)
                db.insert_chunks(doc_id, [{
                    "page": 0,
                    "section": "Image description",
                    "content": description,
                }])
                rag.invalidate()
        analysis["description"] = description
        analysis["indexed"] = bool(description)
        analysis["vision_error"] = vision_error
        analysis["note"] = (
            "The image description was generated and added to the knowledge base."
            if description else
            "Image description is unavailable. Check GROQ_VISION_MODEL and the Groq model access; "
            "deterministic pixel analysis is still available."
        )
        if not description:
            db.create_document(file.filename or "image", Path(file.filename or "image").suffix.lower() or ".image", "image", data)
        return analysis
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
        from api.app.video import analyze_video_file, sample_video_frames
        result = analyze_video_file(temp)
        descriptions = llm.describe_video_frames(sample_video_frames(temp)) if llm.enabled else []
        video_id = db.create_document(file.filename or "video", suffix, "video", data)
        summary = (
            f"Video file {file.filename or 'video'}. Duration: {result['duration_seconds']} seconds. "
            f"Resolution: {result['width']}x{result['height']}. FPS: {result['fps']}. "
            f"Sampled {len(result['sampled_frames'])} frames for brightness, edge density, and scene changes."
        )
        if descriptions:
            summary += " Visual descriptions from representative frames:\n" + "\n".join(descriptions)
        else:
            summary += " No vision description was available; deterministic analysis does not identify objects, speech, or actions."
        db.insert_chunks(video_id, [{"page": 0, "section": "Video analysis", "content": summary}])
        rag.invalidate()
        result["description"] = "\n".join(descriptions) if descriptions else None
        result["indexed"] = True
        result["note"] = "Video analysis and representative-frame descriptions were added to the knowledge base." if descriptions else "Video analysis was added, but visual descriptions require GROQ_API_KEY."
        return result
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        if temp:
            try: os.unlink(temp)
            except OSError: pass
