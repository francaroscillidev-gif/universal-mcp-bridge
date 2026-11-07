# Universal MCP Bridge & Proxy 🌉⚡

<p align="center">
  <img src="assets/icon.svg" alt="Universal MCP Bridge & Proxy Logo" width="180" height="180" />
</p>

<h1 align="center">Universal MCP Bridge &amp; Proxy 🌉⚡</h1>

<p align="center">
  <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License: Apache 2.0" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" /></a>
  <a href="http://localhost:8000/metrics"><img src="https://img.shields.io/badge/metrics-Prometheus-orange.svg" alt="Prometheus Metrics" /></a>
  <a href="http://localhost:8000/healthz"><img src="https://img.shields.io/badge/health-passing-emerald.svg" alt="Health Status" /></a>
</p>

> **The Enterprise-Grade Gateway, Aggregator & Universal Proxy for the Model Context Protocol (MCP). Transform OpenAPI, GraphQL, Documents, Python/Bash scripts, CLIs, Databases (SQLite, PostgreSQL, Redis), and Upstream MCP Servers into secure, federated MCP endpoints on the fly with Multi-Tenant RBAC, Workflow Pipeline Chaining, Cross-Platform Schema Export, Prometheus metrics, and Zero-Config Hot-Reload.**

L'adozione del **Model Context Protocol (MCP)** di Anthropic è lo standard de facto per connettere LLM e agenti intelligenti a tool esterni. **Universal MCP Bridge** posiziona la tua infrastruttura al centro di questo ecosistema, consentendo di governare, orchestrare ed esporre qualsiasi tool con standard enterprise di sicurezza, osservabilità e flessibilità.

---

## ⚡ Installazione 1-Line (Quickstart)

Installa Universal MCP Bridge globalmente su qualsiasi sistema Linux o macOS in pochi secondi:

```bash
curl -fsSL https://raw.githubusercontent.com/francaroscillidev-gif/universal-mcp-bridge/main/install.sh | bash
```

Oppure con [uv](https://github.com/astral-sh/uv):
```bash
git clone https://github.com/francaroscillidev-gif/universal-mcp-bridge.git
cd universal-mcp-bridge
uv sync
```

---

## 🚀 Architettura & Funzionalità Top Tier

1. **Adattatori Multi-Sorgente Universali**:
   - **OpenAPI / REST**: Mappatura automatica di endpoint, path/query params e body JSON.
   - **GraphQL**: Introspezione dello schema (`__schema`), tipizzazione e argomenti.
   - **Documenti & Knowledge Base (`DocumentSearchAdapter`)**: Ricerca fuzzy su cartelle di file (`.md`, `.txt`, `.csv`, `.json`, ecc.) e lettura a chunk paginati.
   - **Federazione MCP-to-MCP (`MCPProxyAdapter`)**: Proxy trasparente per altri server MCP esistenti (es. GitHub MCP, Slack MCP) con wrapping dei nostri controlli di sicurezza.
   - **Script (Python & Bash)**: Ispezione docstring/commenti, argomenti CLI e standard input.
   - **CLI Tools**: Ispezione automatica dei sotto-comandi via `--help` (`git`, `curl`, `jq`, ecc.).
   - **Database Relazionali & In-Memory**:
     - **SQLite**: Schema inspector e query SQL con blocco read-only.
     - **PostgreSQL**: Connection pooling async (`asyncpg`) e ispezione DDL.
     - **Redis**: Navigazione chiavi e recupero tipi complessi (string, hash, list, set).
2. **🔐 Multi-Tenant Role-Based Access Control (RBAC)**:
   - Autenticazione e autorizzazione tramite token **JWT** firmati crittograficamente.
   - Ruoli granulari (`admin`, `analyst`, `agent`) con whitelist e blacklist dinamiche su pattern di tool.
   - Generazione chiavi con comando dedicato: `universal-mcp generate-token`.
3. **⛓️ Multi-Step Workflow Pipeline Chaining (`WorkflowChainer`)**:
   - Concatena tool MCP eterogenei in una singola pipeline logica (es. estrai da DB -> analizza con script Python -> invia via API REST).
   - Risoluzione automatica delle variabili con sintassi `{{step_1.output}}` ed esecuzione non bloccante.
4. **🌐 Cross-Platform Schema Exporter (`SchemaExporter`)**:
   - Esporta all'istante l'intero catalogo dei tool montati in formato:
     - **OpenAI Function Calling / Assistants API** (`--format openai`)
     - **Anthropic Claude Tool Use** (`--format anthropic`)
     - **OpenAPI 3.1 Specification** (`--format openapi`)
5. **🧠 LLM Prompt Optimizer (`PromptOptimizer`)**:
   - Arricchisce semanticamente le descrizioni dei tool seguendo le linee guida di Anthropic e OpenAI, riducendo le allucinazioni e migliorando l'accuratezza del function calling.
6. **🧪 Interactive CLI Testing (`test-tool`)**:
   - Esegui e testa qualsiasi tool montato direttamente da riga di comando per debugging rapido senza avviare LLM.
7. **⏳ Background Async Job Queue (`AsyncJobQueue`)**:
   - Esecuzione asincrona per task e script pesanti con tracciamento stato e tool `job_status(job_id)`.
8. **⚡ Runtime Hot-Mounting & Webhooks Gateway**:
   - Aggiunta di nuovi tool a caldo via REST o Dashboard Web senza riavvio del processo.
   - Ricezione webhook esterni (`/api/webhooks/{source}`) per risvegliare l'agente via prompt notifications.
9. **🛡️ Sicurezza & Resilienza Enterprise**:
   - **Circuit Breaker Pattern**: Isolamento automatico di dipendenze a monte instabili.
   - **Security Sandbox**: Esecuzione asincrona senza shell=True, tokenizzazione `shlex`, blacklist anti-injection e timeout.
   - **Secret & PII Redactor**: Mascheramento automatico di token Bearer, API key e password.
   - **Human-in-the-Loop (HITL)**: Approvazione interattiva su terminale per comandi critici.
   - **Rate Limiting & Response Cache (TTL)**: Protezione da loop agentici e costi API.
10. **Osservabilità & Web Dashboard**:
   - **Live Web Dashboard**: UI moderna su porta 8000 con monitoraggio in tempo reale.
   - **Prometheus `/metrics`**: Integrazione standard Prometheus/Grafana per latenze e volumi.
   - **Healthcheck `/healthz`**: Pronto per Kubernetes liveness/readiness probes.

---

## 🛠️ Comandi CLI Completi

### 1. Test Rapido di un Tool da Terminale
```bash
uv run universal-mcp test-tool --config examples/universal-mcp.yaml --name run_text_analyzer --args '{"args": "Hello World"}'
```

### 2. Avviare la Live Web Dashboard & Gateway
```bash
uv run universal-mcp dashboard --config examples/universal-mcp.yaml --port 8000
```
- Web UI: `http://localhost:8000`
- Metriche Prometheus: `http://localhost:8000/metrics`
- Healthcheck: `http://localhost:8000/healthz`
- Webhook Ingestion: `POST http://localhost:8000/api/webhooks/{source}`

### 3. Esportazione Schema per altri Framework (OpenAI / Claude / OpenAPI)
```bash
# Esporta per OpenAI Assistants o GPT-4o
uv run universal-mcp export-schema --config examples/universal-mcp.yaml --format openai

# Esporta per Claude Tool Use
uv run universal-mcp export-schema --config examples/universal-mcp.yaml --format anthropic

# Esporta come specifica OpenAPI 3.1
uv run universal-mcp export-schema --config examples/universal-mcp.yaml --format openapi --output spec.json
```

### 4. Generazione Token JWT Multi-Tenant (RBAC)
```bash
uv run universal-mcp generate-token --subject my-agent-1 --role analyst
```

### 5. Avvio del Server MCP (Standard I/O o SSE)
```bash
# Modalità standard I/O (Claude Desktop, Cursor, Antigravity) con Prompt Optimization
uv run universal-mcp serve --config examples/universal-mcp.yaml --optimize --transport stdio

# Modalità con Human-in-the-Loop attivo
uv run universal-mcp serve --config examples/universal-mcp.yaml --hitl

# Modalità SSE per microservizi di rete
uv run universal-mcp serve --config examples/universal-mcp.yaml --transport sse --port 8080
```

### 6. Esportare la configurazione 1-Click per Claude Desktop / Cursor
```bash
uv run universal-mcp export-client-config --config examples/universal-mcp.yaml
```

---

## 📖 Guide all'Integrazione

- [🤖 Guida Integrazione Claude Desktop](docs/claude_desktop.md)
- [⚡ Guida Integrazione Cursor IDE](docs/cursor_ide.md)
- [☸️ Manifesto Kubernetes (Deployment & Service)](docs/kubernetes_deployment.yaml)

---

## 🐳 Esecuzione con Docker

```bash
docker compose up --build
```

---

## 🧪 Esecuzione Suite di Test

```bash
uv run pytest
```

---

## 📬 Contact, Support & Commercial Inquiries

If you have questions, feedback, enterprise integration requests, or custom agent governance needs, feel free to reach out directly:

- **Lead Developer & Maintainer**: Franca Roscilli
- **Email**: [francaroscillidev@gmail.com](mailto:francaroscillidev@gmail.com)
- **GitHub**: [@francaroscillidev-gif](https://github.com/francaroscillidev-gif)
- **Bug Reports & Feature Requests**: [Open an issue on GitHub](https://github.com/francaroscillidev-gif/universal-mcp-bridge/issues)

---

## 📜 Licenza

Distribuito sotto licenza **Apache 2.0**. Consulta il file `LICENSE` per maggiori dettagli.
