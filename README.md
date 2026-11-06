# Universal MCP Bridge & Proxy 🌉⚡

[![CI/CD](https://github.com/francaroscillidev-gif/universal-mcp-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/francaroscillidev-gif/universal-mcp-bridge/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

> **Trasforma qualsiasi specifica OpenAPI, script Python/Bash, CLI o Database (SQLite, PostgreSQL, Redis) in un server MCP (Model Context Protocol) di livello enterprise al volo, con sandboxing avanzato, rate limiting, Human-in-the-Loop, live dashboard e zero-config.**

L'adozione del **Model Context Protocol (MCP)** di Anthropic è in rapida ascesa come standard de facto per connettere LLM e agenti a tool esterni. **Universal MCP Bridge** elimina ogni lavoro manuale e permette di esporre istantaneamente qualsiasi risorsa preesistente in un server MCP ad alte prestazioni pronto per la produzione.

---

## 🚀 Architettura & Funzionalità

1. **Adattatori Multi-Sorgente**:
   - **OpenAPI / REST**: Mappa automaticamente endpoint con conversione tipi, query params e body JSON.
   - **Script (Python & Bash)**: Ispezione docstring/commenti, argomenti CLI e standard input.
   - **CLI Tools**: Ispezione automatica dei sotto-comandi tramite `--help` (`git`, `curl`, `jq`, ecc.).
   - **Database Relazionali & In-Memory**:
     - **SQLite**: Schema inspector e query SQL sicure read-only.
     - **PostgreSQL**: Connection pooling async (`asyncpg`) e ispezione DDL.
     - **Redis**: Navigazione chiavi per pattern e recupero valori (stringhe, hash, liste, set).
2. **Sicurezza Enterprise**:
   - **Security Sandbox**: Esecuzione asincrona senza `shell=True`, tokenizzazione `shlex`, blacklist anti-injection, directory containment e timeout.
   - **Human-in-the-Loop (HITL)**: Modalità di conferma manuale/interattiva per comandi sensibili prima dell'esecuzione.
   - **Rate Limiting**: Algoritmo a finestra mobile configurabile.
   - **Response Caching (TTL)**: Cache in-memory per risposte a latenza 0ms e protezione da costi/rate-limit.
3. **Osservabilità & Web Dashboard**:
   - **Live Web Dashboard**: Interfaccia web moderna su porta 8000 con monitoraggio real-time di tool, stato server e feed live dell'audit log.
   - **Audit Log Strutturato**: Scrittura in tempo reale su file `.jsonl` di latenze, argomenti, esiti ed errori.
   - **Hot-Reload Watcher**: Ricaricamento al volo in caso di modifica dei file montati.
4. **CI/CD & Distribuzione**:
   - Workflow GitHub Actions per test multi-OS (Linux, macOS) e rilascio automatico su PyPI.
   - Docker & Docker Compose per deployment cloud immediato.

---

## 🛠️ Comandi CLI

### 1. Avviare la Live Web Dashboard
```bash
uv run universal-mcp dashboard --config examples/universal-mcp.yaml --port 8000
```
Apri il browser su `http://localhost:8000` per monitorare i tool e visualizzare i log live.

### 2. Ispezione dei Tool (dry-run)
```bash
uv run universal-mcp inspect --config examples/universal-mcp.yaml
```

### 3. Avvio del Server MCP (stdio o SSE)
```bash
# Modalità stdio per Claude Desktop, Cursor, Antigravity
uv run universal-mcp serve --config examples/universal-mcp.yaml --transport stdio

# Modalità con Human-in-the-Loop interattivo nel terminale
uv run universal-mcp serve --config examples/universal-mcp.yaml --hitl

# Modalità SSE per microservizi di rete
uv run universal-mcp serve --config examples/universal-mcp.yaml --transport sse --port 8080
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

## 👤 Autore & Contatti

- **Autore**: franca roscilli
- **Email**: [francaroscillidev@gmail.com](mailto:francaroscillidev@gmail.com)
- **GitHub**: [@francaroscillidev-gif](https://github.com/francaroscillidev-gif)

---

## 📜 Licenza

Distribuito sotto licenza **Apache 2.0**. Consulta il file `LICENSE` per maggiori dettagli.
