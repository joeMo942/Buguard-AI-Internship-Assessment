# Buguard Asset Management Backend - AI/LLM Track

A robust, multi-tenant cybersecurity asset management backend powered by FastAPI, PostgreSQL, and LangGraph. This project fulfills the requirements for the Buguard Internship Task (Track B: AI Applications).

## 🚀 Features

- **Multi-Tenancy**: Data is securely partitioned by `org_id` using FastAPI Dependencies and SQLAlchemy filtering.
- **Deduplication Engine**: Robust `/import` endpoint that resolves duplicate asset IDs and merges graph relationships idempotently.
- **Agentic AI Capabilities**:
  1. **NL to SQL/Filter**: Translates natural language questions into structured database queries.
  2. **Risk Scoring**: Context-aware risk summarization based on an asset and its relationships.
  3. **Automated Enrichment**: Analyzes asset metadata and automatically writes back new tags/categories to the database.
  4. **Autonomous Agent**: A ReAct LangGraph agent that dynamically utilizes database lookup tools to answer complex user queries.
  5. **Anti-Hallucination Guardrails**: Real-time post-generation validation that cross-references LLM outputs against the actual database and flags hallucinated assets.

## 🏗️ Architecture

- **Web Framework**: FastAPI (Async)
- **Database**: PostgreSQL with asyncpg driver
- **ORM & Migrations**: SQLAlchemy 2.0 (Async) + Alembic
- **AI/LLM Layer**: LangChain 0.3 + LangGraph (ReAct architecture)
- **LLM Provider**: Gemini 2.5 Pro (via Google GenAI)

## 📦 Setup & Installation

1. Clone the repository.
2. Copy `.env.example` to `.env` and insert your Gemini API Key:
   ```bash
   cp .env.example .env
   # Edit .env and set GEMINI_API_KEY
   ```
3. Boot the environment using Docker Compose:
   ```bash
   docker-compose up --build
   ```
4. The API will be available at `http://localhost:8000`. You can view the interactive Swagger docs at `http://localhost:8000/docs`.

## 🧪 Running Tests & Evals

The project includes a full suite of Pytest unit tests and an AI evaluation harness.
Run them via Docker Compose:
```bash
docker-compose run --rm app pytest -v
```

## 🧠 Technical Assumptions & Design Decisions

1. **Model Selection:** Google's Gemini 2.5 Pro was selected for its massive context window (crucial for injecting large asset summaries as "grounding" context) and native support for structured JSON outputs.
2. **Multi-Tenancy Implementation:** Implemented at the ORM layer using an `org_id` column rather than separate schemas or databases. This is the most scalable approach for SaaS applications with thousands of tenants. The `org_id` is passed via the `X-Org-Id` HTTP header. If omitted, it defaults to `"default"`.
3. **Graph Relationships:** Modeled in a relational database using an adjacency list pattern (`asset_relationships` table). For extreme scale, this could be migrated to a dedicated Graph Database (like Neo4j), but PostgreSQL is sufficient and reduces infrastructure complexity for the MVP.
4. **Anti-Hallucination:** Rather than relying solely on prompt engineering, deterministic guardrails were implemented. The system parses the LLM output for asset IDs (`a123`) and values (`example.com`), and validates them against a pre-fetched set of known good values from the DB.
5. **Agentic Framework:** Due to LangChain 0.3 deprecating `create_react_agent` from the core package, the autonomous agent is built using the newer, state-based `langgraph` framework, ensuring the application is future-proof.
