# GaRC (GraphRAG Automated Risk & Compliance)
> **OUPI Cyber Clinic Contest 2026 Entry** — *Category 2: AI-enabled cybersecurity solution for underserved communities*

GaRC is a dual-engine Explainable AI (XAI) platform designed to make **NIST SP 800-171 compliance assessment** and **network topology modeling** accessible, automated, and explainable for small businesses, non-profits, and underserved organizations lacking dedicated SecOps staff.

---

## 🌟 Key Features & Dual-Engine Architecture

```
                          +-----------------------------------+
                          |      React + Vite Web UI          |
                          |  (Cytoscape.js XAI & Topology)    |
                          +-----------------+-----------------+
                                            |
                         +------------------+------------------+
                         |                                     |
                         v                                     v
         +-------------------------------+     +-------------------------------+
         |    Engine 1: GraphRAG Chat    |     |   Engine 2: NL Topology       |
         |  Preloaded NIST 800-171 KG    |     |  Confidence Scoring & XAI     |
         +---------------+---------------+     +---------------+---------------+
                         |                                     |
                         +------------------+------------------+
                                            |
                                            v
                          +-----------------------------------+
                          |  Pluggable LLM (Gemini / Ollama)  |
                          +-----------------+-----------------+
                                            |
                                            v
                          +-----------------------------------+
                          |    Neo4j Graph DB (Docker)        |
                          +-----------------------------------+
```

### 1. Engine 1: GraphRAG Compliance Assistant & Multi-Hop XAI
- **Preloaded NIST SP 800-171 Knowledge Graph**: Domains, Control Families, Control IDs (e.g., 3.1.1, 3.5.3, 3.13.11), Assessment Objectives, and tailored Small Business Guidance.
- **Explainable AI (XAI) Multi-Hop Paths**: Automatically traverses graph paths `[User Requirement -> NIST Control -> Assessment Objective -> Mitigation]` and visualizes the exact graph traversal using Cytoscape.js alongside step-by-step markdown explanations.

### 2. Engine 2: Natural Language Topology Builder & Interactive Clarification
- **Natural Language Parsing**: Translates plain text descriptions of networks (devices, subnets, NAS, firewalls) into structured Neo4j graph nodes and relationships.
- **Confidence Scoring & Clarification Prompts**: Evaluates confidence for extracted attributes. Low-confidence nodes (e.g., unconfirmed CUI storage or missing MFA) trigger interactive clarification cards before persisting the graph to Neo4j.

### 3. Pluggable LLM Provider System
- Supports **Cloud LLM APIs** (Google Gemini API via `google-genai`) and **100% Offline Local LLMs** (via Ollama) for maximum data privacy.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- Docker (optional, for Neo4j Community container; in-memory fallback included)

### 1. Database (Neo4j Docker Container)
```bash
docker compose up -d
```

### 2. Backend Setup (FastAPI)
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Start FastAPI dev server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
Open your browser at `http://localhost:3000`.

---

## 📄 License
[MIT License](LICENSE)