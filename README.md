# 🧠 LLM Gateway — Intelligent AI Engineering Router

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react)](https://reactjs.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker)](https://docker.com)

A **production-grade, full-stack AI gateway** that intelligently routes LLM prompts across providers (OpenAI, Anthropic, Ollama) based on complexity, verifies output quality using an **LLM-as-a-judge** pattern, auto-escalates failed responses, and tracks cost savings in real time.

---

## 🏗️ Architecture

```
User Prompt
    │
    ▼
┌─────────────────┐
│  FastAPI Gateway │  ← Request validation, CORS, health checks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Classifier    │  ← Rule-based (<50ms): Tier 1 / 2 / 3
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌───────────────────────┐
│  Router Engine  │────▶│ Config Manager (YAML)  │
└────────┬────────┘     │ Hot-reload + checksums │
         │              └───────────────────────┘
         ▼
┌─────────────────┐
│ Provider Adapter│  ← OpenAI / Anthropic / Ollama
│ + Retry/Backoff │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LLM-as-a-Judge  │  ← Quality score 0-10
│   Verifier      │
└────────┬────────┘
         │ score < threshold?
         ▼
┌─────────────────┐
│   Escalator     │  ← Step up to next tier, re-verify
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Cost Engine    │  ← Actual vs GPT-4o baseline savings
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SQLite (async) │  ← WAL mode, full request telemetry
└─────────────────┘
```

---

## ✨ Features

| Feature | Detail |
|---|---|
| **3-Tier Routing** | Tier 1 (Ollama/local) → Tier 2 (GPT-4o-mini) → Tier 3 (GPT-4o) |
| **LLM-as-a-Judge** | Secondary model scores responses 0–10 against quality thresholds |
| **Auto-Escalation** | Failed verifications automatically re-route to a higher-capability tier |
| **Cost Analytics** | Tracks actual spend vs GPT-4o baseline, calculates % savings per request |
| **Hot-Reload Config** | YAML routing table reloads without downtime via SHA-256 checksum polling |
| **Async DB Telemetry** | Full request/verification/escalation logs in aiosqlite with WAL journaling |
| **React Dashboard** | Real-time execution trace, cost charts, tier routing distribution |
| **Docker Ready** | Multi-stage Dockerfile — builds React + Python in one image |

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/AkshatSemwall/LLM-Gateway.git
cd LLM-Gateway
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your API keys:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run (with built-in Mock Server for demo)

```bash
# Terminal 1 — Mock provider server (no API keys needed)
python -m uvicorn scripts.mock_server:app --port 9000

# Terminal 2 — Main API + React dashboard
python -m uvicorn api.main:app --port 8000
```

Open **http://127.0.0.1:8000/dashboard** in your browser.

### 4. Docker (Production)

```bash
docker-compose up --build
```

---

## 🗂️ Project Structure

```
LLM-Gateway/
├── api/
│   ├── main.py                  # FastAPI app, CORS, lifespan, endpoints
│   ├── classifier/              # Rule-based prompt complexity classifier
│   ├── router/                  # Config manager + routing table models
│   ├── providers/               # OpenAI / Anthropic / Ollama adapters
│   ├── verifier/                # LLM judge + escalation logic
│   ├── cost/                    # Cost computation engine
│   ├── database/                # SQLAlchemy models + async repository
│   └── models/                  # Request / Response Pydantic schemas
├── frontend/                    # Vite + React dashboard
│   └── src/
│       ├── App.jsx              # Main UI (Console + Analytics tabs)
│       └── App.css              # Premium dark-mode glassmorphism UI
├── scripts/
│   └── mock_server.py           # Local mock for OpenAI/Anthropic/Ollama
├── config/
│   └── routing_config.yaml      # Tier definitions, model costs, thresholds
├── Dockerfile                   # Multi-stage build (Node + Python)
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 📡 API Reference

### `POST /v1/completions`

```json
{
  "prompt": "Design a distributed rate limiter",
  "quality_hint": "high",
  "verification_mode": "sync"
}
```

**Response:**
```json
{
  "request_id": "req_abc123",
  "output": "...",
  "tier": 3,
  "model_used": "gpt-4o",
  "provider": "openai",
  "prompt_tokens": 108,
  "completion_tokens": 365,
  "latency_ms": 1704.2,
  "cost_usd": 0.00392,
  "savings_usd": 0.0,
  "savings_pct": 0.0,
  "escalated": false,
  "verified": true
}
```

### `GET /health`

```json
{ "status": "healthy", "version": "1.0.0" }
```

---

## 🛠️ Tech Stack

- **Backend:** FastAPI, SQLAlchemy (async), aiosqlite, httpx, Pydantic v2, python-dotenv
- **Frontend:** React 18, Vite, lucide-react
- **Providers:** OpenAI Chat Completions, Anthropic Messages API, Ollama local inference
- **DevOps:** Docker multi-stage build, docker-compose, uvicorn

---

## 🔧 Configuration

Edit `config/routing_config.yaml` to change models, costs, and quality thresholds. The config manager auto-reloads on file change — no restart needed.

```yaml
routing:
  tier1:
    primary:
      provider: ollama
      model_name: llama3.2:1b
      cost_per_1k_input: 0.0
      cost_per_1k_output: 0.0
  tier2:
    primary:
      provider: openai
      model_name: gpt-4o-mini
      ...
  tier3:
    primary:
      provider: openai
      model_name: gpt-4o
      ...

quality_thresholds:
  tier1: 6.5
  tier2: 7.0
  tier3: 8.0
```

---

## 📄 License

MIT
