# Custom Chatbot

A personal CLI chatbot built to experiment with LangChain, tool calling, and a PostgreSQL-backed chat history with session titles. It supports user accounts, streaming responses, file/URL reading, and a minimal in-memory RAG workflow.

## Purpose

The goal is to learn and iterate on practical LangChain features while keeping the codebase small, understandable, and easy to extend.

## Features

- User registration/login with bcrypt
- Session management (create/resume/delete, title generation)
- Chat history stored in Postgres
- Tool calling (time, math, file reading, URL reading)
- Basic RAG per session (chunking, embeddings, retrieval, context injection)
- User profile injected into the system prompt
- Streaming-like output and clean Ctrl+C handling

## How To Use

1) Install dependencies.
2) Set up the database and environment variables.
3) Run the app:

```bash
uv run ./chatbot/main.py
```

During a chat you can ask for a file or URL, and the model will load it using tools, index it, and then answer based on the retrieved content.

## .env

Create a `.env` file in the project root with:

```
DATABASE_URL=postgresql://user@localhost:5432/...
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=qwen2.5-7b-instruct # thats a model I use
```

Notes:
- `LMSTUDIO_EMBEDDING_MODEL` falls back to `LMSTUDIO_MODEL` if not set.
- The DB schema is created automatically on startup.
