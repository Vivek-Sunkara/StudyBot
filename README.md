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

An optional Groq LLM is used for natural-language generation, local calculator tool
calling, and image description. When configured, image descriptions are indexed in
SQLite and can be used by later RAG questions. Without a Groq key, deterministic RAG
and pixel-level image analysis still work, but the system cannot identify image
content or describe objects and scenes.

## Run

Python 3.12+:

    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # Linux/macOS: source .venv/bin/activate
    pip install -r requirements.txt

Copy `.env.example` to `.env` and set `MONGODB_URI` and `MONGODB_DATABASE` for persistent library and chat data. You may also set `GROQ_API_KEY`.
For image descriptions, optionally set `GROQ_VISION_MODEL` (the default is
`qwen/qwen3.8-27b`).

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

Vercel can deploy Next.js and FastAPI together. Set `MONGODB_URI`, `MONGODB_DATABASE`,
`GROQ_API_KEY`, and `GROQ_MODEL` as Vercel environment variables. Add the deployment
network access rule in MongoDB Atlas.

The included 4 MB upload limit is deliberate because serverless request payloads
are constrained. For large production video uploads, use direct object storage and
asynchronous processing.

SQLite is retained as a local fallback when `MONGODB_URI` is not set. MongoDB stores
documents, images, videos, and previous chat sessions for deployed environments.

## Multimodal boundary

Text and documents are fully searchable. Images and videos always receive
deterministic computer-vision analysis. With Groq vision configured, images also
receive a factual visual description that is added to the knowledge base for RAG.
The system does not pretend to perform arbitrary OCR, speech transcription, or
human-level visual understanding, and it does not describe images when the vision
service is unavailable.
Images and videos always receive deterministic computer-vision analysis. With Groq
vision configured, images also receive a factual visual description that is added to
the knowledge base for RAG. The system does not pretend to perform arbitrary OCR,
speech transcription, or human-level visual understanding, and it does not describe
images when the vision service is unavailable.
