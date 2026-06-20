import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from fastapi import FastAPI
from pydantic import BaseModel
from agent.graph import agent_graph
from ingestion.k8s_watcher import get_unhealthy_pods

app = FastAPI(title="DevOps Incident Resolution Agent")

class AlertRequest(BaseModel):
    alert: str

@app.post("/chat")
def chat(req: AlertRequest):
    initial_state = {
        "alert": req.alert,
        "context": [],
        "rca": "",
        "confidence": "",
        "commands": [],
        "retry_count": 0
    }
    result = agent_graph.invoke(initial_state)
    return {
        "rca": result["rca"],
        "confidence": result["confidence"],
        "retry_count": result["retry_count"]
    }

@app.get("/scan")
def scan_cluster():
    alerts = get_unhealthy_pods()
    results = []
    for alert in alerts:
        initial_state = {
            "alert": alert,
            "context": [],
            "rca": "",
            "confidence": "",
            "commands": [],
            "retry_count": 0
        }
        result = agent_graph.invoke(initial_state)
        results.append({
            "alert": alert,
            "rca": result["rca"],
            "confidence": result["confidence"]
        })
    return {"detected_issues": results}

@app.get("/")
def root():
    return {"status": "DevOps Incident Agent is running"}