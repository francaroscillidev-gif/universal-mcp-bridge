# Universal MCP Bridge & Proxy 🌉⚡

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Prometheus Metrics](https://img.shields.io/badge/metrics-Prometheus-orange.svg)](http://localhost:8000/metrics)
[![Health Status](https://img.shields.io/badge/health-passing-emerald.svg)](http://localhost:8000/healthz)

> **The Enterprise-Grade Gateway & Universal Proxy for the Model Context Protocol (MCP). Transform OpenAPI, GraphQL, Python/Bash scripts, CLIs, and Databases (SQLite, PostgreSQL, Redis) into secure MCP servers on the fly with Multi-Tenant RBAC, Workflow Pipeline Chaining, Cross-Platform Schema Export (OpenAI, Claude, OpenAPI), Prometheus metrics, Circuit Breakers, and Zero-Config Hot-Reload.**

L'adozione del **Model Context Protocol (MCP)** di Anthropic è lo standard de facto per connettere LLM e agenti intelligenti a tool esterni. **Universal MCP Bridge** posiziona la tua infrastruttura al centro di questo ecosistema, consentendo di governare, orchestrare ed esporre qualsiasi tool con standard enterprise di sicurezza, osservabilità e flessibilità.

---

## 🚀 Architettura & Funzionalità Top Tier

1. **Adattatori Multi-Sorgente Universali**:
   - **OpenAPI / REST**: Mappatura automatica di endpoint, path/query params e body JSON.
   - **GraphQL**: Introspezione dello schema (`__schema`), tipizzazione e argomenti.
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
6. **⏳ Background Async Job Queue (`AsyncJobQueue`)**:
   - Esecuzione asincrona per task e script pesanti con tracciamento stato e tool `job_status(job_id)`.
7. **⚡ Runtime Hot-Mounting & Webhooks Gateway**:
   - Aggiunta di nuovi tool a caldo via REST o Dashboard Web senza riavvio del processo.
   - Ricezione webhook esterni (`/api/webhooks/{source}`) per risvegliare l'agente via prompt notifications.
8. **🛡️ Sicurezza & Resilienza Enterprise**:
   - **Circuit Breaker Pattern**: Isolamento automatico di dipendenze a monte instabili.
   - **Security Sandbox**: Esecuzione asincrona senza shell=True, tokenizzazione `shlex`, blacklist anti-injection e timeout.
   - **Secret & PII Redactor**: Mascheramento automatico di token Bearer, API key e password.
   - **Human-in-the-Loop (HITL)**: Approvazione interattiva su terminale per comandi critici.
   - **Rate Limiting & Response Cache (TTL)**: Protezione da loop agentici e costi API.
9. **Osservabilità & Web Dashboard**:
   - **Live Web Dashboard**: UI moderna su porta 8000 con monitoraggio in tempo reale.
   - **Prometheus `/metrics`**: Integrazione standard Prometheus/Grafana per latenze e volumi.
   - **Healthcheck `/healthz`**: Pronto per Kubernetes liveness/readiness probes.

---

## 🛠️ Comandi CLI Completi

### 1. Avviare la Live Web Dashboard & Gateway
```bash
uv run universal-mcp dashboard --config examples/universal-mcp.yaml --port 8000
```
- Web UI: `http://localhost:8000`
- Metriche Prometheus: `http://localhost:8000/metrics`
- Healthcheck: `http://localhost:8000/healthz`
- Webhook Ingestion: `POST http://localhost:8000/api/webhooks/{source}`

### 2. Esportazione Schema per altri Framework (OpenAI / Claude / OpenAPI)
```bash
# Esporta per OpenAI Assistants o GPT-4o
uv run universal-mcp export-schema --config examples/universal-mcp.yaml --format openai

# Esporta per Claude Tool Use
uv run universal-mcp export-schema --config examples/universal-mcp.yaml --format anthropic

# Esporta come specifica OpenAPI 3.1
uv run universal-mcp export-schema --config examples/universal-mcp.yaml --format openapi --output spec.json
```

### 3. Generazione Token JWT Multi-Tenant (RBAC)
```bash
uv run universal-mcp generate-token --subject my-agent-1 --role analyst
```

### 4. Ottimizzazione delle descrizioni per gli Agenti AI
```bash
uv run universal-mcp optimize-prompts --config examples/universal-mcp.yaml
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
