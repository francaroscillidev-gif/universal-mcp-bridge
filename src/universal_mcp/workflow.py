import os
import json
import uuid
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class PipelineStep(BaseModel):
    step_id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:6]}")
    tool_name: str
    args_template: Dict[str, Any] = Field(default_factory=dict, description="Arguments with template substitution like {{step_1.output}}")

class WorkflowPipeline(BaseModel):
    pipeline_id: str
    name: str
    description: str = ""
    steps: List[PipelineStep]

class WorkflowChainer:
    """
    Executes multi-step pipelines combining multiple heterogeneous MCP tools
    (e.g., Query SQLite -> Filter with Python script -> Post to REST API)
    with output parameter forwarding and error propagation.
    """
    def __init__(self, bridge):
        self.bridge = bridge

    def _substitute_templates(self, template: Any, context: Dict[str, Any]) -> Any:
        if isinstance(template, str):
            res = template
            for key, val in context.items():
                pattern = f"{{{{{key}}}}}"
                if pattern in res:
                    val_str = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
                    res = res.replace(pattern, val_str)
            return res
        elif isinstance(template, dict):
            return {k: self._substitute_templates(v, context) for k, v in template.items()}
        elif isinstance(template, list):
            return [self._substitute_templates(i, context) for i in template]
        return template

    async def execute_pipeline(self, pipeline: WorkflowPipeline, initial_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context: Dict[str, Any] = dict(initial_inputs or {})
        step_outputs: Dict[str, Any] = {}
        execution_trace = []

        start_time = time.time()
        for idx, step in enumerate(pipeline.steps):
            step_start = time.time()
            resolved_args = self._substitute_templates(step.args_template, context)

            try:
                # Call MCP tool
                res = await self.bridge.server.call_tool(step.tool_name, resolved_args)
                text_out = ""
                if hasattr(res, "content"):
                    for c in res.content:
                        text_out += getattr(c, "text", str(c))
                else:
                    text_out = str(res)

                # Try parsing as JSON for smart forwarding
                try:
                    parsed_val = json.loads(text_out)
                except Exception:
                    parsed_val = text_out

                context[step.step_id] = parsed_val
                context[f"step_{idx+1}"] = parsed_val
                step_outputs[step.step_id] = parsed_val

                execution_trace.append({
                    "step_id": step.step_id,
                    "tool": step.tool_name,
                    "status": "SUCCESS",
                    "duration_ms": round((time.time() - step_start) * 1000, 2)
                })
            except Exception as e:
                execution_trace.append({
                    "step_id": step.step_id,
                    "tool": step.tool_name,
                    "status": "FAILED",
                    "error": str(e),
                    "duration_ms": round((time.time() - step_start) * 1000, 2)
                })
                return {
                    "success": False,
                    "pipeline_id": pipeline.pipeline_id,
                    "failed_step": step.step_id,
                    "error": str(e),
                    "trace": execution_trace
                }

        return {
            "success": True,
            "pipeline_id": pipeline.pipeline_id,
            "total_duration_ms": round((time.time() - start_time) * 1000, 2),
            "final_output": step_outputs.get(pipeline.steps[-1].step_id),
            "step_outputs": step_outputs,
            "trace": execution_trace
        }
