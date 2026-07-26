import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agent.graph import agent_graph
from agent.remediation import (
    execute_remediation,
    get_allowed_actions,
    remediation_history,
)
from ingestion.k8s_watcher import get_unhealthy_pods, get_all_pods_summary

app = FastAPI(title="DevOps Incident Resolution Agent - Grafana Monitor")

# Ensure static directory exists
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

import re
from typing import Optional, List

class AlertRequest(BaseModel):
    alert: str
    pod_name: Optional[str] = None
    namespace: Optional[str] = None
    containers: Optional[List[str]] = None
    status_reason: Optional[str] = None
    diagnostics: Optional[List[str]] = None

def build_initial_state(alert, **incident):
    pod_name = incident.get("pod_name", "")
    namespace = incident.get("namespace", "")
    containers = incident.get("containers", [])

    # Extract pod_name & namespace from alert text if not provided explicitly
    if not pod_name:
        pm = re.search(r"\bpod\s+([a-zA-Z0-9\-_]+)", alert, re.IGNORECASE)
        if pm:
            pod_name = pm.group(1)

    if not namespace:
        nm = re.search(r"\bnamespace\s+([a-zA-Z0-9\-_]+)", alert, re.IGNORECASE)
        if nm:
            namespace = nm.group(1)

    if not containers and pod_name:
        containers = [None]

    return {
        "alert": alert,
        "context": [],
        "rca": "",
        "confidence": "",
        "commands": [],
        "retry_count": 0,
        "pod_name": pod_name,
        "namespace": namespace,
        "containers": containers,
        "status_reason": incident.get("status_reason", ""),
        "diagnostics": incident.get("diagnostics", []),
        "logs": incident.get("logs", []),
        "log_evidence": incident.get("log_evidence", ""),
        "logs_used": incident.get("logs_used", False),
        "log_attempted": incident.get("log_attempted", False),
        "log_fetch_error": incident.get("log_fetch_error", ""),
    }

@app.get("/")
def get_dashboard():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "DevOps Incident Agent is running", "ui": "static/index.html missing"}

@app.get("/pods")
def get_pods():
    pods = get_all_pods_summary()
    total_pods = len(pods)
    healthy_pods = sum(1 for p in pods if p.get("is_healthy"))
    unhealthy_pods = total_pods - healthy_pods
    health_pct = round((healthy_pods / total_pods * 100), 1) if total_pods > 0 else 100.0

    namespaces = sorted(list(set(p.get("namespace", "default") for p in pods)))

    return {
        "stats": {
            "total_pods": total_pods,
            "healthy_pods": healthy_pods,
            "unhealthy_pods": unhealthy_pods,
            "health_pct": health_pct,
        },
        "namespaces": namespaces,
        "pods": pods
    }

@app.post("/chat")
def chat(req: AlertRequest):
    initial_state = build_initial_state(
        req.alert,
        pod_name=req.pod_name or "",
        namespace=req.namespace or "",
        containers=req.containers or [],
        status_reason=req.status_reason or "",
        diagnostics=req.diagnostics or []
    )
    result = agent_graph.invoke(initial_state)
    return {
        "rca": result["rca"],
        "confidence": result["confidence"],
        "retry_count": result["retry_count"],
        "logs_used": result.get("logs_used", False),
        "remediation_action": result.get("remediation_action", {"action": "none", "reason": ""}),
    }

@app.get("/scan")
def scan_cluster():
    incidents = get_unhealthy_pods()
    results = []
    for incident in incidents:
        initial_state = build_initial_state(**incident)
        result = agent_graph.invoke(initial_state)
        results.append({
            "alert": incident.get("alert", f"Pod {incident.get('pod_name')} is unhealthy"),
            "pod_name": incident.get("pod_name", "unknown"),
            "namespace": incident.get("namespace", "default"),
            "status_reason": incident.get("status_reason", "Unhealthy"),
            "rca": result["rca"],
            "confidence": result["confidence"],
            "retry_count": result["retry_count"],
            "logs_used": result.get("logs_used", False),
            "log_fetch_error": result.get("log_fetch_error", ""),
            "remediation_action": result.get("remediation_action", {"action": "none", "reason": ""}),
        })
    return {"detected_issues": results}


# ─────────────────────────────────────────────────
# Remediation Endpoints
# ─────────────────────────────────────────────────

class RemediationRequest(BaseModel):
    action_type: str
    pod_name: str
    namespace: str
    replicas: Optional[int] = 1
    verify: Optional[bool] = True
    verify_timeout: Optional[int] = 60

@app.get("/remediations/actions")
def list_remediation_actions():
    """Return the catalogue of allowed remediation action types."""
    return {"allowed_actions": get_allowed_actions()}

@app.post("/remediations/execute")
def run_remediation(req: RemediationRequest):
    """Execute a validated remediation action on a pod/deployment."""
    result = execute_remediation(
        action_type=req.action_type,
        pod_name=req.pod_name,
        namespace=req.namespace,
        replicas=req.replicas or 1,
        verify=req.verify if req.verify is not None else True,
        verify_timeout=req.verify_timeout or 60,
    )
    return {
        "success": result.success,
        "action_type": result.action_type,
        "pod_name": result.pod_name,
        "namespace": result.namespace,
        "command": result.command,
        "output": result.output,
        "error": result.error,
        "verification_status": result.verification_status,
        "verification_msg": result.verification_msg,
        "executed_at": result.executed_at,
    }

@app.get("/remediations/history")
def get_remediation_history():
    """Return the audit log of all remediation actions executed this session."""
    return {"history": list(reversed(remediation_history))}
