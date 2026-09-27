from fastapi.responses import JSONResponse
import io
import os
import logging
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd

from api.app.data_tools import analyze_csv

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo.errors import ConfigurationError, PyMongoError, ServerSelectionTimeoutError

from api.app.config import settings
from api.app.db import Database, MongoDatabase
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

def _safe_mongodb_error(exc):
    message = str(exc)
    return message.replace(settings.mongodb_uri, "<redacted-mongodb-uri>") if settings.mongodb_uri else message

@app.exception_handler(PyMongoError)
async def mongodb_error_handler(request, exc):
    error_type = type(exc).__name__
    if isinstance(exc, ServerSelectionTimeoutError):
        category = "server selection timeout; check Atlas Network Access, DNS, and TLS"
    elif isinstance(exc, ConfigurationError):
        category = "configuration error; check MONGODB_URI and database credentials"
    else:
        category = "database operation failure"
    logger.error("MongoDB %s (%s): %s", category, error_type, _safe_mongodb_error(exc))
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "MongoDB is unavailable. Check MONGODB_URI, MongoDB Atlas Network Access, "
                "and the local network/TLS connection."
            )
        },
    )

db = MongoDatabase(settings.mongodb_uri, settings.mongodb_database) if settings.mongodb_uri else Database(settings.database_path)
rag = RAG(db, settings.top_k)
llm = LLM()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: Optional[str] = None
    language: Optional[str] = None

class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    language: str = Field(min_length=2, max_length=40)

class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)

class DataAnalysisRequest(BaseModel):
    file_id: str
    operation: str
    parameters: dict = Field(default_factory=dict)


def _local_data_fallback(question: str, database, language: str):
    text = (question or "").lower()

    def normalized(value):
        return "".join(character for character in str(value).lower() if character.isalnum())

    csv_docs = [
        doc for doc in database.list_documents()
        if (doc.get("file_type") or "").lower() == ".csv" or str(doc.get("filename") or "").lower().endswith(".csv")
    ]
    if not csv_docs:
        return "I could not find any uploaded CSV file to inspect directly."

    target_name = None
    for doc in csv_docs:
        filename = str(doc.get("filename") or "").lower()
        if filename in text or text in filename:
            target_name = doc["filename"]
            break
    if target_name is None:
        target_name = csv_docs[0]["filename"]

    doc = database.document_info(target_name)
    if doc is None:
        return "I could not locate the CSV file in the uploaded study data."

    payload = database.document_bytes(target_name)
    if not payload:
        return "The CSV file is present, but its contents are not available for inspection."

    try:
        frame = pd.read_csv(io.BytesIO(payload))
    except Exception:
        return "I could not parse the uploaded CSV file."

    columns = list(frame.columns)
    if not columns:
        return "I inspected the CSV, but it does not contain any columns."

    if any(token in text for token in ["column names", "columns", "header", "headers", "field", "fields", "name", "names"]) and not any(token in text for token in ["average", "avg", "mean", "sum", "total", "count", "describe", "distribution", "unique"]):
        return "I inspected the uploaded CSV and the columns are: " + ", ".join(columns)

    if any(token in text for token in ["average", "avg", "mean"]):
        normalized_text = normalized(text)
        match = next((column for column in columns if normalized(column) in normalized_text), None)
        if match is None:
            numeric = [c for c in columns if pd.api.types.is_numeric_dtype(frame[c])]
            if len(numeric) == 1:
                match = numeric[0]
        if match is None:
            return "I inspected the CSV, but I could not find a numeric column to average."
        values = pd.to_numeric(frame[match], errors="coerce").dropna()
        if values.empty:
            return f"The {match} column does not contain numeric values that can be averaged."
        average_value = float(values.mean())
        return f"The average of the {match} column is {average_value:.6g}."

    if any(token in text for token in ["sum", "total"]):
        normalized_text = normalized(text)
        match = next((column for column in columns if normalized(column) in normalized_text), None)
        if match is None:
            numeric = [c for c in columns if pd.api.types.is_numeric_dtype(frame[c])]
            if len(numeric) == 1:
                match = numeric[0]
        if match is None:
            return "I inspected the CSV, but I could not find a numeric column to sum."
        total = pd.to_numeric(frame[match], errors="coerce").sum()
        return f"The total of the {match} column is {float(total):.6g}."

    if any(token in text for token in ["describe", "summary", "overview"]):
        summary = analyze_csv(payload, "summary")
        rows = summary.get("rows", 0)
        return f"I inspected the uploaded CSV and found {rows} rows with the following columns: {', '.join(columns)}."

    result = analyze_csv(payload, "summary")
    rows = result.get("rows", 0)
    return f"I inspected the uploaded CSV and found {rows} rows with the following columns: {', '.join(columns)}."


@app.get("/api/health")
def health():
    if os.getenv("VERCEL") and not settings.mongodb_uri:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "detail": "MONGODB_URI is not configured for the Vercel deployment."},
        )
    db.ping()
    return {"ok": True, "groq_configured": llm.enabled,
            "database": "mongodb" if settings.mongodb_uri else "sqlite",
            "documents": db.document_count(), "chunks": db.chunk_count()}

@app.post("/api/translate")
def translate(req: TranslationRequest):
    if not llm.enabled:
        raise HTTPException(503, "Translation requires a configured language model")
    try:
        return {"text": llm.translate(req.text, req.language)}
    except Exception as exc:
        logger.exception("Translation request failed")
        raise HTTPException(502, "Translation failed") from exc

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

@app.delete("/api/chats/{conversation_id}")
def delete_chat(conversation_id: str):
    if not db.delete_conversation(conversation_id):
        raise HTTPException(404, "Chat not found")
    rag.invalidate()
    return {"ok": True}

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    from api.app.documents import extract_document

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md", ".csv"}:
        raise HTTPException(400, "Supported files: PDF, DOCX, TXT, MD, CSV")
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    try:
        if suffix == ".csv":
            chunks = [{"page": 0, "section": "Data file", "content": "CSV data file available for local analysis."}]
        else:
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
    lang = req.language or detect_script(req.message)
    history = db.get_messages(req.conversation_id) if req.conversation_id else []
    route = classify_query(req.message, bool(history))
    media_kind = requested_media_kind(req.message)
    results = [] if route in {"conversation", "calculator", "data"} else rag.search(
        retrieval_query(req.message, history, route),
        include_all=requests_document_summary(req.message),
        kinds={media_kind} if media_kind else None,
    )
    if llm.enabled:
        try:
            data_files = [
                str(doc.get("filename")) for doc in db.list_documents()
                if (doc.get("file_type") or "").lower() == ".csv"
                or str(doc.get("filename") or "").lower().endswith(".csv")
            ]
            answer, calls = llm.answer(
                req.message, lang, results, lambda name, args: execute_tool(name, args, db), TOOL_SCHEMAS,
                history=history, route=route, data_files=data_files,
            )
            mode = "groq+local-rag"
        except Exception:
            if route == "conversation":
                answer = "Hello! I can help you study, explain concepts, and work with your uploaded notes."
            elif route == "calculator":
                answer = "I could not complete the calculation safely."
            elif route == "data":
                answer = _local_data_fallback(req.message, db, lang)
            else:
                answer = rag.fallback(req.message, results, lang)
            calls = []
            mode = "local-rag-fallback"
    else:
        if route == "calculator":
            answer, calls = "Calculator requests require a configured language model.", []
        elif route == "conversation":
            answer, calls = "Hello! I can help you study, explain concepts, and work with your uploaded notes.", []
        elif route == "data":
            answer, calls = _local_data_fallback(req.message, db, lang), []
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
    from api.app.images import analyze_image_bytes

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
