# Universal MCP Bridge & Proxy 🌉⚡

> **Trasforma qualsiasi specifica OpenAPI, script Python/Bash, CLI o Database SQLite in un server MCP (Model Context Protocol) al volo, con sandboxing avanzato, rate limiting, audit logging e zero-config scaffolding.**

L'adozione del **Model Context Protocol (MCP)** di Anthropic è in rapida ascesa come standard de facto per connettere LLM e agenti a tool esterni. **Universal MCP Bridge** elimina il lavoro manuale e permette di esporre istantaneamente qualsiasi risorsa preesistente in un server MCP ad alte prestazioni pronto per la produzione.

---

## 🚀 Nuove Funzionalità & Architettura

1. **Adattatore Database SQLite (`SQLiteAdapter`)**:
   - Connessione immediata a qualsiasi file SQLite (`.db`, `.sqlite`).
   - Generazione automatica di tool per esplorazione dello schema (`db_<name>_schema`) ed esecuzione query protette (`db_<name>_query`).
   - Modalità read-only sicura con blocco delle query mutative (`INSERT`, `UPDATE`, `DELETE`, `DROP`).
2. **Security & Rate Limiting a Finestra Mobile**:
   - Protezione da overflow di chiamate LLM con policy configurabile (`max_requests` in `window_seconds`).
   - Sandboxing senza `shell=True` con tokenizzazione `shlex`, blacklist di espressioni pericolose (`rm -rf`, fork bomb, injection) e whitelist di comandi.
3. **Audit Logging Strutturato (JSONL)**:
   - Tracciamento temporale di ogni invocazione di tool, argomenti, tempo di latenza (`duration_ms`), esito e messaggi d'errore.
4. **Esposizione Dinamica di Risorse MCP (`bridge://manifest`)**:
   - Gli LLM possono leggere direttamente lo stato e il catalogo del server come MCP Resource standard.
5. **Comando `universal-mcp init`**:
   - Generazione istantanea del file template `universal-mcp.yaml`.
6. **Containerizzazione Docker & Docker Compose**:
   - Immagine container multi-stage pronta per il deployment in cloud (SSE mode o proxy HTTP).

---

## 🛠️ Comandi CLI

### 1. Inizializzare un nuovo progetto
```bash
uv run universal-mcp init --name "Agent-Production-Bridge"
```

### 2. Ispezione dei Tool (dry-run)
```bash
uv run universal-mcp inspect --config examples/universal-mcp.yaml
```

Output:
```text
                  Universal MCP Bridge - Discovered Tools (7)                   
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Tool Name         ┃ Parameters                  ┃ Description                ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ findPetsByStatus  │ status: string              │ Finds Pets by status       │
│ getPetById        │ petId: integer              │ Find pet by ID             │
│ run_text_analyzer │ args: string, stdin_input   │ Calculate SHA256 checksum  │
│ run_sys_health    │ args: string                │ Quick system health check  │
│ db_sample_schema  │ none                        │ Inspect tables & schema    │
│ db_sample_query   │ query: string, limit: int   │ Run SQL query (READ-ONLY)  │
│ exec_curl         │ args: string                │ Executes 'curl'            │
└───────────────────┴─────────────────────────────┴────────────────────────────┘
```

### 3. Avvio del Server MCP (stdio o SSE)
```bash
# Modalità standard I/O per desktop client (Claude, Cursor, Antigravity)
uv run universal-mcp serve --config examples/universal-mcp.yaml --transport stdio

# Modalità SSE per rete o microservizi
uv run universal-mcp serve --config examples/universal-mcp.yaml --transport sse --port 8080
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

