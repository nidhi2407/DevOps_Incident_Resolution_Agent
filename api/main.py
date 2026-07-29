import os
import traceback
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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
    try:
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
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "detail": f"Agent error: {type(e).__name__}: {e}",
            "traceback": tb
        })

@app.get("/scan")
def scan_cluster():
    try:
        incidents = get_unhealthy_pods()
        results = []
        for incident in incidents:
            try:
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
            except Exception as pod_err:
                results.append({
                    "pod_name": incident.get("pod_name", "unknown"),
                    "namespace": incident.get("namespace", "default"),
                    "status_reason": incident.get("status_reason", "Unhealthy"),
                    "rca": f"⚠️ Agent error for this pod: {pod_err}",
                    "confidence": "Low",
                    "retry_count": 0,
                    "logs_used": False,
                    "log_fetch_error": str(pod_err),
                    "remediation_action": {"action": "none", "reason": "Agent error"},
                })
        return {"detected_issues": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "detail": f"Scan error: {type(e).__name__}: {e}"
        })


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

@app.get("/pods/status/{namespace}/{pod_name}")
def get_pod_status(namespace: str, pod_name: str):
    """
    Return the live status of a specific pod.
    Used by the UI to verify real recovery after an autofix action.
    """
    try:
        from kubernetes import client, config
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        v1 = client.CoreV1Api()

        # For standalone pods (delete_pod action) look up by exact name
        try:
            pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            phase = pod.status.phase or "Unknown"
            statuses = pod.status.container_statuses or []
            ready_count = sum(1 for s in statuses if s.ready)
            total_count = len(statuses) if statuses else 1
            is_running = (phase == "Running") and (ready_count == total_count)
            status_reason = phase
            for s in statuses:
                if not s.ready:
                    if s.state.waiting:
                        status_reason = s.state.waiting.reason or phase
                    elif s.state.terminated:
                        status_reason = s.state.terminated.reason or phase
            return {
                "found": True,
                "pod_name": pod_name,
                "namespace": namespace,
                "status": status_reason,
                "phase": phase,
                "ready": f"{ready_count}/{total_count}",
                "is_running": is_running,
            }
        except Exception:
            pass

        # For deployments (restart_deployment / rollout_undo) find replacement pods by label
        pods = v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app={pod_name.rsplit('-', 2)[0]}"
        )
        if not pods.items:
            # Broader search — any pod whose name starts with the deployment name prefix
            all_pods = v1.list_namespaced_pod(namespace=namespace)
            # Extract deployment name: strip the last two hash segments
            parts = pod_name.rsplit('-', 2)
            prefix = parts[0] if len(parts) >= 3 else pod_name
            matching = [p for p in all_pods.items if p.metadata.name.startswith(prefix)]
            pods.items = matching

        if pods.items:
            # Return the newest pod's status
            newest = sorted(pods.items, key=lambda p: p.metadata.creation_timestamp or 0, reverse=True)[0]
            phase = newest.status.phase or "Unknown"
            statuses = newest.status.container_statuses or []
            ready_count = sum(1 for s in statuses if s.ready)
            total_count = len(statuses) if statuses else 1
            is_running = (phase == "Running") and (ready_count == total_count)
            status_reason = phase
            for s in statuses:
                if not s.ready:
                    if s.state.waiting:
                        status_reason = s.state.waiting.reason or phase
                    elif s.state.terminated:
                        status_reason = s.state.terminated.reason or phase
            return {
                "found": True,
                "pod_name": newest.metadata.name,
                "namespace": namespace,
                "status": status_reason,
                "phase": phase,
                "ready": f"{ready_count}/{total_count}",
                "is_running": is_running,
            }

        return {"found": False, "pod_name": pod_name, "namespace": namespace,
                "status": "NotFound", "is_running": False}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

