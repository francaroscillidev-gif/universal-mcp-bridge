import asyncio
import uuid
import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class AsyncJobStatus(BaseModel):
    job_id: str
    tool_name: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None

class AsyncJobQueue:
    """
    In-memory background job execution queue for long-running MCP tools
    (e.g., large data migrations, heavy scripts, deep SQL queries).
    Allows agents to submit jobs and poll for completion asynchronously.
    """
    def __init__(self):
        self.jobs: Dict[str, AsyncJobStatus] = {}

    def submit_job(self, tool_name: str, coro_func, *args, **kwargs) -> str:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = AsyncJobStatus(job_id=job_id, tool_name=tool_name, status="PENDING")
        self.jobs[job_id] = job

        asyncio.create_task(self._run_job(job_id, coro_func, *args, **kwargs))
        return job_id

    async def _run_job(self, job_id: str, coro_func, *args, **kwargs):
        job = self.jobs[job_id]
        job.status = "RUNNING"
        try:
            result = await coro_func(*args, **kwargs)
            job.status = "COMPLETED"
            job.result = str(result)
        except Exception as e:
            job.status = "FAILED"
            job.error = str(e)
        finally:
            job.completed_at = time.time()

    def get_job(self, job_id: str) -> Optional[AsyncJobStatus]:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[AsyncJobStatus]:
        return list(self.jobs.values())
