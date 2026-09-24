# StudyRAG

A real multimodal RAG study assistant built with Next.js + FastAPI.

## No pretrained supporting models

This project does not use Whisper, CLIP, BERT, Sentence Transformers, Qwen-VL, LLaVA,
OCR models, embedding models, or downloaded pretrained models.

The supporting pipeline is deterministic:
- TF-IDF/BM25-style lexical retrieval
- PDF/DOCX/TXT/MD extraction
- safe AST calculator
- OpenCV image analysis
- OpenCV video frame/scene analysis
- Unicode script detection

An optional Groq LLM is used only for natural-language generation and local calculator
tool calling. Without a Groq key, deterministic RAG still works.

## Run

Python 3.12+:

    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # Linux/macOS: source .venv/bin/activate
    pip install -r requirements.txt

Copy `.env.example` to `.env` and optionally set `GROQ_API_KEY`.

Install Node dependencies:

    cd frontend
    npm install
    cd ..

Run API directly:

    uvicorn api.index:app --reload --port 8000

Or use Vercel locally so frontend and FastAPI share one origin:

    npm install -g vercel
    vercel dev

## Test

    pytest -q

## Deployment

Vercel can deploy Next.js and FastAPI together. Set `GROQ_API_KEY` and `GROQ_MODEL`
as Vercel environment variables.

The included 4 MB upload limit is deliberate because serverless request payloads
are constrained. For large production video uploads, use direct object storage and
asynchronous processing.

SQLite is included for a self-contained project. On serverless infrastructure,
persistent multi-user data should later be moved to a hosted SQL database.

## Multimodal boundary

Text and documents are fully searchable. Images and videos receive deterministic
computer-vision analysis. Because no pretrained vision/speech models are used,
the system does not pretend to perform arbitrary OCR, speech transcription, or
human-level visual understanding.
