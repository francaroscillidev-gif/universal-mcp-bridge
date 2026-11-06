import os
import json
from typing import List, Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

def create_dashboard_app(bridge) -> FastAPI:
    app = FastAPI(title="Universal MCP Bridge Dashboard")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/status")
    async def get_status():
        return {
            "name": bridge.name,
            "tool_count": len(bridge.registered_tools),
            "tools": [t.model_dump() for t in bridge.registered_tools],
            "security": {
                "timeout": bridge.security.policy.timeout_seconds,
                "has_whitelist": bridge.security.policy.allowed_commands is not None,
                "has_rate_limit": bridge.rate_limiter is not None,
                "has_cache": bridge.cache is not None,
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
            # Execute through MCP Server call_tool
            res = await bridge.server.call_tool(tool_name, payload)
            # res is CallToolResult from MCP
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

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Universal MCP Bridge - Live Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
  <div class="max-w-7xl mx-auto px-4 py-8">
    <header class="flex justify-between items-center pb-6 border-b border-slate-700">
      <div>
        <h1 class="text-3xl font-extrabold tracking-tight text-indigo-400">🌉 Universal MCP Bridge</h1>
        <p class="text-sm text-slate-400 mt-1">Autonomous Agent Tool Server & Proxy Dashboard</p>
      </div>
      <div id="stats-badge" class="bg-indigo-950 border border-indigo-500/30 px-4 py-2 rounded-lg text-sm">
        Loading status...
      </div>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
      <!-- Tools list -->
      <div class="lg:col-span-2">
        <h2 class="text-xl font-bold mb-4 flex items-center gap-2">🛠️ Active Tools (<span id="tool-count">0</span>)</h2>
        <div id="tools-container" class="space-y-4">
          <div class="p-6 bg-slate-800 rounded-xl animate-pulse">Loading tools...</div>
        </div>
      </div>

      <!-- Live Audit Feed -->
      <div>
        <h2 class="text-xl font-bold mb-4 flex items-center gap-2">📜 Live Audit Log</h2>
        <div id="audit-feed" class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 h-[600px] overflow-y-auto font-mono text-xs space-y-3">
          <div class="text-slate-500">Waiting for invocations...</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    async function loadData() {
      try {
        const [statusRes, auditRes] = await Promise.all([
          fetch('/api/status'),
          fetch('/api/audit')
        ]);
        const status = await statusRes.json();
        const audit = await auditRes.json();

        // Update Header
        document.getElementById('stats-badge').innerHTML = `
          <span class="text-emerald-400 font-semibold">● ACTIVE</span> | 
          Server: <strong>${status.name}</strong> | 
          Tools: <strong>${status.tool_count}</strong>
        `;
        document.getElementById('tool-count').innerText = status.tool_count;

        // Render Tools
        const container = document.getElementById('tools-container');
        container.innerHTML = status.tools.map(t => `
          <div class="p-5 bg-slate-800 border border-slate-700/80 rounded-xl hover:border-indigo-500/50 transition">
            <div class="flex justify-between items-start">
              <div>
                <h3 class="font-mono text-lg font-bold text-indigo-300">${t.name}</h3>
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
        `).join('');

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
