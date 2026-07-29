# GaRC (Graph augmented Risk & Compliance)
> **OUPI Cyber Clinic Contest 2026 Entry** — *Category 2: AI-enabled cybersecurity solution for underserved communities*

GaRC is a guided Explainable AI (XAI) platform designed to make **NIST SP 800-171 Rev 3 compliance assessment** and **network topology modeling** accessible, automated, and explainable for small businesses, non-profits, and underserved organizations lacking dedicated SecOps staff.

---

## 🌟 Key Features & 3-Step Guided Compliance Architecture

```
                          +-----------------------------------+
                          |      FastAPI Web UI Dashboard     |
                          |  (Cytoscape.js XAI & Topology)    |
                          +-----------------+-----------------+
                                            |
                          +-----------------+-----------------+
                          |  Welcome Landing & Guided Setup   |
                          +-----------------+-----------------+
                                            |
         +----------------------------------+----------------------------------+
         |                                  |                                  |
         v                                  v                                  v
+------------------------+      +------------------------+      +------------------------+
|  Step 1: Network       |      |  Step 2: Compliance    |      |  Step 3: NIST 800-171  |
|  Topology Builder      | ---> |  Assistant (GraphRAG)  | ---> |  Gap Scorecard         |
|  (Sub-ms Extraction)   |      |  (Intent Topology Audit)|      |  (Real-Time Readiness) |
+------------------------+      +------------------------+      +------------------------+
                                            |
                                            v
                          +-----------------------------------+
                          |  Pluggable LLM Provider System    |
                          |   (OpenRouter / Gemini / Ollama)  |
                          +-----------------+-----------------+
                                            |
                                            v
                          +-----------------------------------+
                          |  Neo4j DB (or In-Memory Fallback) |
                          +-----------------------------------+
```

### 1. Welcome Landing & 3-Step Guided Workflow
- **Welcome Choice Screen**: Choose to either map your network architecture first (Recommended) or jump straight to compliance Q&A.
- **Visual Workflow Stepper**: Seamless breadcrumb navigation with directional step indicators:
  $$\text{Step 1: 🗺️ Network Topology} \longrightarrow \text{Step 2: 💬 Compliance Assistant (GraphRAG)} \longrightarrow \text{Step 3: 📊 Gap Scorecard}$$

### 2. Step 1: High-Speed Network Topology Builder
- **Sub-Millisecond Natural Language Extraction**: Instantly extracts network entities (workstations, NAS storage, routers, subnets) and security attributes (MFA, CUI data, encryption) in $<0.01\text{s}$.
- **Interactive Clarification Cards**: Automatically identifies ambiguous security configurations (e.g. unconfirmed MFA or storage encryption) and prompts the user for 1-click confirmation before persisting the topology graph.

### 3. Step 2: GraphRAG Compliance Copilot & Intent-Driven Topology Audits
- **"Guide, Don't Prescribe" Intuition Engine**: GaRC acts as a CISO's intuition engine and an auditor's assistant rather than a definitive remediation bot. It spots pattern anomalies, highlights potential scope creep traps, and separates shared responsibilities between your on-premise hardware and cloud providers.
- **Intent-Driven Active Topology Audits**: Ask prompts like *"audit my network topology"* or *"assess my setup"*. The Copilot automatically traces paths across your active devices from Step 1, generating specific **Investigative Flags** and actionable prompts for human assessors rather than prescriptive assumptions.
- **Preloaded NIST SP 800-171 Rev 3 Knowledge Graph**: Official NIST CPRT dataset containing all 17 Control Families, 97 Security Controls, Assessment Objectives, and Small Business Guidance.
- **Explainable AI (XAI) Multi-Hop Paths & Interactive Tracing**: Generates clean Markdown answers with inline `[Trace Control_ID]` links. Clicking any trace link dynamically prunes and highlights the reasoning sequence on the Cytoscape canvas.

### 4. Step 3: NIST SP 800-171 Gap Scorecard
- **Dynamic Readiness Scoring**: Computes your overall compliance readiness percentage based on active network topology attributes.

---

## ⚡ Easiest Way to Run (Python Only — Zero Node.js Required!)

GaRC includes a **built-in standalone Web UI** served directly by FastAPI. You do **NOT** need Node.js, npm, or Docker to run it!

### Step 1: Set Up Backend Environment & Dependencies
```powershell
cd backend

# Create & activate virtual environment (Windows PowerShell):
python -m venv venv
.\venv\Scripts\activate

# On Linux/macOS:
# source venv/bin/activate

# Install requirements:
pip install -r requirements.txt
```

### Step 2: Configure API Key (.env)
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```
Open `.env` and add your **OpenRouter API Key** (or Gemini API Key):
```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct
```

### Step 3: Run FastAPI App

**Ensure your terminal is inside the `backend` directory:**
```powershell
cd backend
.\venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8001
```

### Step 4: Open Browser
Open **[http://localhost:8001](http://localhost:8001)** in your web browser! 🎉

*(Note: If Docker / Neo4j is not running, GaRC automatically boots in **In-Memory Fallback Mode**, preloaded with the full official NIST SP 800-171 Rev 3 CPRT dataset, so everything works out of the box!)*

---

## 🛠️ Alternative Setup Options

### Option A: Advanced React + Vite Frontend (Requires Node.js)
If you prefer running the Vite React development server separately:

1. **Start Backend Server**:
   ```powershell
   cd backend
   .\venv\Scripts\activate
   python -m uvicorn app.main:app --reload --port 8001
   ```
2. **Start Frontend Dev Server**:
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```
3. Open browser at **[http://localhost:3000](http://localhost:3000)**.

### Option B: Local Neo4j Container Stack (Docker)
If you want to run a live dedicated Neo4j instance instead of in-memory fallback:
```powershell
docker compose up -d
```

---

## 📄 License
[Apache 2.0 License](LICENSE)
