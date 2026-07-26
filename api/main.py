import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from fastapi import FastAPI
from pydantic import BaseModel
from agent.graph import agent_graph
from ingestion.k8s_watcher import get_unhealthy_pods

app = FastAPI(title="DevOps Incident Resolution Agent")

class AlertRequest(BaseModel):
    alert: str

def build_initial_state(alert, **incident):
    return {
        "alert": alert,
        "context": [],
        "rca": "",
        "confidence": "",
        "commands": [],
        "retry_count": 0,
        "pod_name": incident.get("pod_name", ""),
        "namespace": incident.get("namespace", ""),
        "containers": incident.get("containers", []),
        "status_reason": incident.get("status_reason", ""),
        "diagnostics": incident.get("diagnostics", []),
        "logs": incident.get("logs", []),
        "log_evidence": incident.get("log_evidence", ""),
        "logs_used": incident.get("logs_used", False),
        "log_attempted": incident.get("log_attempted", False),
        "log_fetch_error": incident.get("log_fetch_error", ""),
    }

@app.post("/chat")
def chat(req: AlertRequest):
    initial_state = build_initial_state(req.alert)
    result = agent_graph.invoke(initial_state)
    return {
        "rca": result["rca"],
        "confidence": result["confidence"],
        "retry_count": result["retry_count"],
        "logs_used": result.get("logs_used", False)
    }

@app.get("/scan")
def scan_cluster():
    incidents = get_unhealthy_pods()
    results = []
    for incident in incidents:
        initial_state = build_initial_state(**incident)
        result = agent_graph.invoke(initial_state)
        results.append({
            "alert": incident["alert"],
            "pod_name": incident["pod_name"],
            "namespace": incident["namespace"],
            "status_reason": incident["status_reason"],
            "rca": result["rca"],
            "confidence": result["confidence"],
            "retry_count": result["retry_count"],
            "logs_used": result.get("logs_used", False),
            "log_fetch_error": result.get("log_fetch_error", "")
        })
    return {"detected_issues": results}

@app.get("/")
def root():
    return {"status": "DevOps Incident Agent is running"}
