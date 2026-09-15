# GaRC (GraphRAG Automated Risk & Compliance) — Project Context & Session Summary

> **Document Purpose**: Complete reference summarizing architecture decisions, user conversations, recent implementations, active components, and future directions for GaRC.

---

## 1. Project Vision & Target Audience

* **Target Audience**: Small-to-Medium Businesses (SMBs) without dedicated cybersecurity teams (Dental/Healthcare Clinics, Law/CPA Firms, Defense/CNC Subcontractors, Non-Profits) and **University Cyber Clinic Student Assessors**.
* **Core Problem Solved**: NIST SP 800-171 Rev 3 and CMMC Level 2 compliance assessments are historically cryptic, expensive, and overwhelming. GaRC demystifies compliance into a **3-step guided visual workflow**:
  1. **Build / Pick Network Topology** (Small Biz Presets, Drag-and-Drop Palette, or Everyday Natural Language Prompt).
  2. **Answer 1-Click Clarifications & Run Compliance Audit**.
  3. **Get Traffic-Light Readiness, Top 3 High-Impact Fixes, and Printable Executive Report**.

---

## 2. Key Architecture & Strategic Decisions

1. **Zero-Node Single Runtime**:
   * Standardized around a single, polished frontend served directly by FastAPI from `backend/app/static/index.html`.
   * Zero Node.js / npm build requirements for end-users. Single startup command: `uvicorn app.main:app --reload`.
2. **5 Core Technical Families (NIST SP 800-171 Rev 3 Focus)**:
   * `03.01` Access Control (AC)
   * `03.05` Identification & Authentication (IA)
   * `03.08` Media Protection (MP)
   * `03.13` System & Communications Protection (SC)
   * `03.14` System & Information Integrity (SI)
3. **Deterministic Fallback + GraphRAG XAI**:
   * Evaluates network facts (firewall existence, MFA flags, CUI storage flags, encryption, subnet boundary separation) deterministically so the application operates seamlessly even offline or without LLM keys.
4. **VLAN & Subnet Alignment**:
   * Subnets/VLANs represent Layer 2/3 security boundaries mapped 1-to-1 in accordance with NIST SP 800-171 control `03.13.05`.

---

## 3. Work Accomplished & Recent Enhancements

### A. Subnet Compound Grouping (Visual Containers)
* **Compound Boundary Boxes**: Subnets (e.g., `Wired Clinic LAN`, `Staff Wi-Fi`, `Patient Guest Wi-Fi`) render as translucent container boxes (`:parent`) in Cytoscape with dashed borders.
* **Nested Child Devices**: Workstations, laptops, and local servers sit physically inside their containing subnet box, eliminating redundant connecting lines.
* **1-Click Subnet Assignment**: Devices can be reassigned between subnets or boundary networks via dropdown in the Device Inspector and the Add Device modal.

### B. Clean Vector Geometric Shapes (Zero Emojis & Zero 404s)
* Replaced emojis with native Cytoscape vector shapes:
  * 💻 **Workstations / Devices**: `round-rectangle` (Cyan/Sky Blue)
  * 🛡️ **Firewalls / Gateways**: `octagon` (Rose Red)
  * 🗄️ **Storage / NAS**: `barrel` (Amber)
  * 🖥️ **Servers**: `round-rectangle` (Indigo)
  * ☁️ **Cloud / VPN**: `hexagon` (Cyan)
  * 📄 **CUI Data Assets**: `rhomboid` (Gold)
* Eliminated raw inline SVG image requests, completely silencing all 404 errors in the FastAPI console.
* Added native inline favicon and FastAPI 204 No Content `/favicon.ico` route.

### C. User-Controlled "Run Compliance Audit" Workflow
* Disabled disruptive automatic background audits on every minor click.
* Added prominent **`🚀 Run NIST SP 800-171 Audit`** CTA button so users can build/edit at their own pace and evaluate on-demand.

### D. Smart Zoom & Screen-Fit Polish
* **Normal 1:1 Scale Bounding**: Single workstations added to an empty canvas render at natural scale (`1.0x`) instead of being blown up to 1000% zoom.
* **Full-Height Dashboard (`100vh`)**: Fixed three-column responsive layout without vertical page scrolling.
* **Empty Workspace Action**: 1-click **"Clear Workspace"** button to start fresh from a blank canvas.
* **Device Deletion**: Prominent **"Delete Device"** button in Inspector and `✕` delete icons in the Active Devices list.

### E. 3-Tab Main Center Hub
1. **`🗺️ Network Map`**: Interactive architecture graph with Dagre flow layouts, auto-fit, and zoom.
2. **`❓ Clarifying Questions`** *(with live counter badge)*:
   * **Network Security Clarifications**: 1-click Yes/No resolvers for CUI storage, MFA, and firewalls.
   * **Assessor Interview Checklist**: Tailored NIST SP 800-171 Rev 3 questions for Cyber Clinic students to ask small business owners.
3. **`🔍 AI Compliance Trace`**: GraphRAG reasoning tree linking Query $\to$ Family $\to$ Control $\to$ Objective status.

### F. 1-Click Executive Assessment Report
* Modal dialog producing a clean, print-ready (`window.print()`) Executive Compliance & Action Report with overall readiness gauge, Top 3 High-Impact Fixes, and assessor checklists.

---

## 4. Key Files Reference Map

| Component | File Path | Description |
| :--- | :--- | :--- |
| **Frontend SPA** | [`backend/app/static/index.html`](file:///c:/Users/al3xa/Desktop/garc/backend/app/static/index.html) | React + Cytoscape + Dagre standalone UI |
| **API Endpoints** | [`backend/app/main.py`](file:///c:/Users/al3xa/Desktop/garc/backend/app/main.py) | FastAPI routes for templates, topology, audit, and export |
| **Topology Engine** | [`backend/app/engine_topology/parser.py`](file:///c:/Users/al3xa/Desktop/garc/backend/app/engine_topology/parser.py) | NL parser, template loader, subnet mapping, node/edge mutations |
| **Small Biz Templates**| [`backend/app/engine_topology/templates.py`](file:///c:/Users/al3xa/Desktop/garc/backend/app/engine_topology/templates.py) | Pre-configured realistic templates (Clinic, Law Firm, CNC, Non-Profit) |
| **XAI Reasoner** | [`backend/app/engine_graphrag/xai_reasoner.py`](file:///c:/Users/al3xa/Desktop/garc/backend/app/engine_graphrag/xai_reasoner.py) | 5-Family parallel auditor, Top 3 Fixes, assessor checklist, XAI graph |
| **Integration Tests** | [`backend/tests/test_api_integration.py`](file:///c:/Users/al3xa/Desktop/garc/backend/tests/test_api_integration.py) | Automated test suite validating end-to-end API workflows |

---

## 5. Verification Status

* **Pytest Test Suite**: `100% Pass Rate` (`tests/test_api_integration.py` passing).
* **Console Logs**: Clean, zero 404 errors, zero background crashes.
* **Server Execution**: Running smoothly on `http://127.0.0.1:8000`.

---

## 6. Future Directions & Next Steps

1. **OSCAL & CMMC Export**: Export assessment findings to standard OSCAL JSON / CMMC Level 2 System Security Plan (SSP) format.
2. **Policy Document Ingestion**: Allow small businesses to drag-and-drop existing policy PDFs (e.g. Employee Handbooks, Incident Response Plans) to automatically verify non-technical controls.
3. **Additional Industry Templates**: Add pre-configured templates for Retail / Point-of-Sale (POS) and Engineering / CAD Design firms.
