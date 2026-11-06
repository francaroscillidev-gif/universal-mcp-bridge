import os
import json
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, Response, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from universal_mcp.security.metrics import get_prometheus_metrics
from universal_mcp.registry import DynamicToolRegistry
from universal_mcp.webhook import WebhookDispatcher

def create_dashboard_app(bridge, webhook_secret: Optional[str] = None) -> FastAPI:
    app = FastAPI(title="Universal MCP Bridge Dashboard & Gateway")
    registry = DynamicToolRegistry(bridge)
    webhook_dispatcher = WebhookDispatcher(secret_token=webhook_secret)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/metrics")
    async def metrics():
        data, content_type = get_prometheus_metrics()
        return Response(content=data, media_type=content_type)

    @app.get("/healthz")
    async def health_check():
        return {
            "status": "healthy",
            "server": bridge.name,
            "tool_count": len(bridge.registered_tools),
            "timestamp": time.time()
        }

    @app.get("/api/status")
    async def get_status():
        cb_status = {}
        for name, cb in bridge.circuit_breakers.items():
            cb_status[name] = {"state": cb.state, "failures": cb.failure_count}

        return {
            "name": bridge.name,
            "tool_count": len(bridge.registered_tools),
            "tools": [t.model_dump() for t in bridge.registered_tools],
            "circuit_breakers": cb_status,
            "security": {
                "timeout": bridge.security.policy.timeout_seconds,
                "has_whitelist": bridge.security.policy.allowed_commands is not None,
                "has_rate_limit": bridge.rate_limiter is not None,
                "has_cache": bridge.cache is not None,
                "has_hitl": bridge.hitl is not None,
                "redact_secrets": bridge.security.policy.redact_secrets,
            }
        }

    @app.get("/api/audit")
    async def get_audit(limit: int = 50):
        log_file = bridge.audit_logger.log_file
        if not log_file or not os.path.exists(log_file):
            return {"logs": []}
        logs = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
        except Exception:
            pass
        return {"logs": logs[-limit:]}

    @app.post("/api/tools/{tool_name}/execute")
    async def execute_tool(tool_name: str, request: Request):
        payload = await request.json()
        target_tool = next((t for t in bridge.registered_tools if t.name == tool_name), None)
        if not target_tool:
            return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})

        try:
            res = await bridge.server.call_tool(tool_name, payload)
            text_contents = []
            if hasattr(res, "content"):
                for c in res.content:
                    if hasattr(c, "text"):
                        text_contents.append(c.text)
                    else:
                        text_contents.append(str(c))
                return {"success": not getattr(res, "isError", False), "result": "\n".join(text_contents)}
            return {"success": True, "result": str(res)}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    # Hot-Mount Tool API
    @app.post("/api/registry/mount")
    async def hot_mount(request: Request):
        body = await request.json()
        m_type = body.get("type")
        target = body.get("target")
        if not m_type or not target:
            raise HTTPException(status_code=400, detail="Missing 'type' or 'target'")

        if m_type == "script":
            result = registry.register_script_tool(target)
        elif m_type == "openapi":
            result = registry.register_openapi_tool(target, base_url=body.get("base_url"))
        elif m_type == "sqlite":
            result = registry.register_sqlite_tool(target, read_only=body.get("read_only", True))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported hot-mount type: {m_type}")

        return result

    # Inbound Webhook Listener
    @app.post("/api/webhooks/{source}")
    async def receive_webhook(source: str, request: Request, authorization: Optional[str] = Header(None)):
        if not webhook_dispatcher.verify_auth(authorization):
            raise HTTPException(status_code=401, detail="Invalid webhook authentication token")

        try:
            payload = await request.json()
        except Exception:
            payload = {"raw": (await request.body()).decode(errors="replace")}

        event_type = request.headers.get("x-event-type") or request.headers.get("x-github-event") or "generic"
        result = webhook_dispatcher.process_incoming_event(source, event_type, payload)
        return result

    @app.get("/api/webhooks/history")
    async def webhook_history():
        return {"events": webhook_dispatcher.history}

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Universal MCP Bridge - Live Dashboard & Gateway</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
  <div class="max-w-7xl mx-auto px-4 py-8">
    <header class="flex justify-between items-center pb-6 border-b border-slate-700">
      <div>
        <h1 class="text-3xl font-extrabold tracking-tight text-indigo-400">🌉 Universal MCP Bridge</h1>
        <p class="text-sm text-slate-400 mt-1">Autonomous Agent Tool Server, Hot-Mount Gateway & Webhook Ingestion</p>
      </div>
      <div class="flex items-center gap-3">
        <a href="/metrics" target="_blank" class="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-600 px-3 py-1.5 rounded text-amber-300 font-mono">
          📊 Prometheus /metrics
        </a>
        <a href="/healthz" target="_blank" class="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-600 px-3 py-1.5 rounded text-emerald-300 font-mono">
          💚 /healthz
        </a>
        <div id="stats-badge" class="bg-indigo-950 border border-indigo-500/30 px-4 py-2 rounded-lg text-sm">
          Loading status...
        </div>
      </div>
    </header>

    <!-- Hot Mount Quick Bar -->
    <div class="mt-6 p-4 bg-slate-800/60 border border-slate-700 rounded-xl flex items-center justify-between gap-4">
      <div class="flex items-center gap-3 w-full">
        <span class="text-xs font-bold text-indigo-300 uppercase tracking-wider">⚡ Hot-Mount Tool:</span>
        <select id="mount-type" class="bg-slate-900 border border-slate-700 text-xs rounded px-2.5 py-1.5 text-slate-200">
          <option value="script">Script (.py/.sh)</option>
          <option value="openapi">OpenAPI Spec (URL/JSON)</option>
          <option value="sqlite">SQLite Database (.db)</option>
        </select>
        <input id="mount-target" type="text" placeholder="Path or URL (e.g. ./scripts/report.py)" class="bg-slate-900 border border-slate-700 text-xs rounded px-3 py-1.5 text-slate-200 flex-1">
        <button onclick="hotMountTool()" class="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-1.5 rounded transition">
          Mount Instantly
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-6">
      <!-- Tools list -->
      <div class="lg:col-span-2">
        <h2 class="text-xl font-bold mb-4 flex items-center gap-2">🛠️ Active Tools (<span id="tool-count">0</span>)</h2>
        <div id="tools-container" class="space-y-4">
          <div class="p-6 bg-slate-800 rounded-xl animate-pulse">Loading tools...</div>
        </div>
      </div>

      <!-- Live Audit & Webhooks Feed -->
      <div class="space-y-6">
        <div>
          <h2 class="text-xl font-bold mb-4 flex items-center gap-2">📜 Live Audit Log</h2>
          <div id="audit-feed" class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 h-[350px] overflow-y-auto font-mono text-xs space-y-3">
            <div class="text-slate-500">Waiting for invocations...</div>
          </div>
        </div>

        <div>
          <h2 class="text-xl font-bold mb-4 flex items-center gap-2">📡 Inbound Webhooks</h2>
          <div id="webhook-feed" class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 h-[250px] overflow-y-auto font-mono text-xs space-y-3">
            <div class="text-slate-500">No events yet. Post to /api/webhooks/{source}</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    async function hotMountTool() {
      const type = document.getElementById('mount-type').value;
      const target = document.getElementById('mount-target').value.trim();
      if (!target) return alert('Please enter target path or URL');

      try {
        const res = await fetch('/api/registry/mount', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({type, target})
        });
        const data = await res.json();
        if (data.success) {
          alert(`Successfully mounted tools: ${data.tools.join(', ')}`);
          document.getElementById('mount-target').value = '';
          loadData();
        } else {
          alert('Mount error: ' + JSON.stringify(data));
        }
      } catch (e) {
        alert('Failed: ' + e);
      }
    }

    async function loadData() {
      try {
        const [statusRes, auditRes, webhookRes] = await Promise.all([
          fetch('/api/status'),
          fetch('/api/audit'),
          fetch('/api/webhooks/history')
        ]);
        const status = await statusRes.json();
        const audit = await auditRes.json();
        const webhooks = await webhookRes.json();

        // Update Header
        document.getElementById('stats-badge').innerHTML = `
          <span class="text-emerald-400 font-semibold">● ACTIVE</span> | 
          Server: <strong>${status.name}</strong> | 
          Tools: <strong>${status.tool_count}</strong>
        `;
        document.getElementById('tool-count').innerText = status.tool_count;

        // Render Tools
        const container = document.getElementById('tools-container');
        container.innerHTML = status.tools.map(t => {
          const cb = status.circuit_breakers && status.circuit_breakers[t.name];
          const cbBadge = cb && cb.state === 'OPEN' 
            ? '<span class="bg-rose-500/20 text-rose-300 border border-rose-500/40 px-2 py-0.5 rounded text-[10px]">CIRCUIT OPEN</span>'
            : '<span class="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-2 py-0.5 rounded text-[10px]">HEALTHY</span>';

          return `
          <div class="p-5 bg-slate-800 border border-slate-700/80 rounded-xl hover:border-indigo-500/50 transition">
            <div class="flex justify-between items-start">
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="font-mono text-lg font-bold text-indigo-300">${t.name}</h3>
                  ${cbBadge}
                </div>
                <p class="text-sm text-slate-300 mt-1">${t.description}</p>
              </div>
            </div>
            <div class="mt-4 pt-3 border-t border-slate-700/50 flex flex-wrap gap-2 text-xs">
              <span class="text-slate-400 self-center">Params:</span>
              ${t.parameters.length ? t.parameters.map(p => `
                <span class="bg-slate-700/80 px-2 py-1 rounded text-emerald-300 font-mono">
                  ${p.name}: <span class="text-slate-300">${p.type}</span> ${p.required ? '<span class="text-rose-400">*</span>': ''}
                </span>
              `).join('') : '<span class="text-slate-500 italic">none</span>'}
            </div>
          </div>
          `;
        }).join('');

        // Render Audit Logs
        const auditBox = document.getElementById('audit-feed');
        if (audit.logs.length) {
          auditBox.innerHTML = audit.logs.slice().reverse().map(l => `
            <div class="p-2.5 rounded bg-slate-900 border ${l.success ? 'border-emerald-500/30' : 'border-rose-500/40'}">
              <div class="flex justify-between text-slate-400 text-[10px]">
                <span>${l.timestamp}</span>
                <span class="${l.success ? 'text-emerald-400' : 'text-rose-400'}">${l.duration_ms}ms</span>
              </div>
              <div class="text-indigo-300 font-bold mt-1">${l.tool}</div>
              <div class="text-slate-400 truncate mt-0.5">${JSON.stringify(l.args)}</div>
              ${l.error ? `<div class="text-rose-400 mt-1">${l.error}</div>` : ''}
            </div>
          `).join('');
        }

        // Render Webhooks
        const webhookBox = document.getElementById('webhook-feed');
        if (webhooks.events.length) {
          webhookBox.innerHTML = webhooks.events.slice().reverse().map(w => `
            <div class="p-2.5 rounded bg-slate-900 border border-indigo-500/30">
              <div class="flex justify-between text-slate-400 text-[10px]">
                <span class="text-amber-400 font-bold">${w.source.toUpperCase()}</span>
                <span class="text-slate-300 font-mono">${w.event_type}</span>
              </div>
              <div class="text-slate-400 truncate mt-1 text-[11px]">${JSON.stringify(w.payload)}</div>
            </div>
          `).join('');
        }
      } catch (e) {
        console.error('Failed to load dashboard data:', e);
      }
    }

    loadData();
    setInterval(loadData, 3000);
  </script>
</body>
</html>"""
        return HTMLResponse(content=html)

    return app
