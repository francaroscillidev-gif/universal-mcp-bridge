# Universal MCP Bridge & Proxy 🌉⚡

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Prometheus Metrics](https://img.shields.io/badge/metrics-Prometheus-orange.svg)](http://localhost:8000/metrics)
[![Health Status](https://img.shields.io/badge/health-passing-emerald.svg)](http://localhost:8000/healthz)

> **Trasforma qualsiasi specifica OpenAPI, endpoint GraphQL, script Python/Bash, CLI o Database (SQLite, PostgreSQL, Redis) in un server MCP (Model Context Protocol) di livello enterprise al volo, con Prompt Optimization per LLM, Background Async Job Queue, Hot-Mounting a runtime, Webhook Ingestion, Prometheus metrics, Circuit Breaker, live dashboard e zero-config.**

L'adozione del **Model Context Protocol (MCP)** di Anthropic è lo standard de facto per connettere LLM e agenti a tool esterni. **Universal MCP Bridge** elimina ogni lavoro manuale e permette di esporre e gestire istantaneamente qualsiasi risorsa preesistente in un server MCP ad alte prestazioni pronto per la produzione.

---

## 🚀 Architettura & Funzionalità

1. **Adattatori Multi-Sorgente**:
   - **OpenAPI / REST**: Mappa automaticamente endpoint con conversione tipi, query params e body JSON.
   - **GraphQL**: Introspezione automatica schema (`__schema`), mappatura campi e argomenti.
   - **Script (Python & Bash)**: Ispezione docstring/commenti, argomenti CLI e standard input.
   - **CLI Tools**: Ispezione automatica dei sotto-comandi tramite `--help` (`git`, `curl`, `jq`, ecc.).
   - **Database Relazionali & In-Memory**:
     - **SQLite**: Schema inspector e query SQL sicure read-only.
     - **PostgreSQL**: Connection pooling async (`asyncpg`) e ispezione DDL.
     - **Redis**: Navigazione chiavi per pattern e recupero valori (stringhe, hash, liste, set).
2. **🧠 LLM Prompt Optimizer (`PromptOptimizer`)**:
   - Riscrive e arricchisce semanticamente le descrizioni dei tool e dei parametri usando le linee guida ufficiali Anthropic/OpenAI, specificando formati di ritorno ed eliminando ambiguità per gli agenti AI.
3. **⏳ Background Async Job Queue (`AsyncJobQueue`)**:
   - Esecuzione non bloccante in background per task computazionali lunghi, migrazioni o script pesanti con polling di stato (`job_status`).
4. **⚡ Runtime Hot-Mounting & Dynamic Registry**:
   - Monta nuovi script, API o database a caldo via REST API (`/api/registry/mount`) o direttamente dall'interfaccia grafica della Dashboard, **senza riavviare il server MCP**.
5. **📡 Inbound Webhooks & Event Ingestion (`/api/webhooks/{source}`)**:
   - Ricevi eventi asincroni (GitHub push, Stripe payments, Datadog alerts) e trasformali in prompt notification strutturate pronte per il risveglio dell'agente LLM.
6. **Sicurezza & Resilienza Enterprise**:
   - **Circuit Breaker Pattern**: Isolamento automatico dei tool a monte in caso di guasti ripetuti.
   - **Security Sandbox**: Esecuzione asincrona senza `shell=True`, tokenizzazione `shlex`, blacklist anti-injection, directory containment e timeout.
   - **Secret & PII Redactor**: Mascheramento automatico di token Bearer, API key e password da risposte e log di audit.
   - **Human-in-the-Loop (HITL)**: Modalità di conferma manuale/interattiva per comandi sensibili prima dell'esecuzione.
   - **Rate Limiting**: Algoritmo a finestra mobile configurabile.
   - **Response Caching (TTL)**: Cache in-memory per risposte a latenza 0ms e protezione da costi/rate-limit.
7. **Osservabilità & Web Dashboard**:
   - **Live Web Dashboard**: Interfaccia web moderna su porta 8000 con monitoraggio real-time di tool, stato server, feed webhooks e audit log.
   - **Prometheus `/metrics`**: Metriche native per Prometheus / Grafana (`mcp_tool_calls_total`, `mcp_tool_execution_duration_seconds`, `mcp_cache_hits_total`, `mcp_rate_limit_exceeded_total`).
   - **Healthcheck `/healthz`**: Endpoint di liveness/readiness per Kubernetes e Docker.
   - **Audit Log Strutturato**: Scrittura in tempo reale su file `.jsonl` di latenze, argomenti, esiti ed errori.

---

## 🛠️ Comandi CLI

### 1. Ottimizzazione delle descrizioni per gli Agenti AI
```bash
uv run universal-mcp optimize-prompts --config examples/universal-mcp.yaml
```

### 2. Avviare la Live Web Dashboard & Gateway
```bash
uv run universal-mcp dashboard --config examples/universal-mcp.yaml --port 8000
```
- Dashboard Web: `http://localhost:8000`
- Metriche Prometheus: `http://localhost:8000/metrics`
- Healthcheck: `http://localhost:8000/healthz`
- Endpoint Webhooks: `POST http://localhost:8000/api/webhooks/{source}`

### 3. Avvio del Server MCP (con opzione `--optimize`)
```bash
# Modalità stdio con ottimizzazione semantica automatica dei prompt
uv run universal-mcp serve --config examples/universal-mcp.yaml --optimize --transport stdio

# Con Human-in-the-Loop interattivo
uv run universal-mcp serve --config examples/universal-mcp.yaml --hitl
```

### 4. Esportare la configurazione per Claude Desktop / Cursor
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
