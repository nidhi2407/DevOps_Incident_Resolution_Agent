from typing import List, TypedDict

class AgentState(TypedDict, total=False):
    alert: str              # raw incoming alert
    context: List[str]      # retrieved runbook chunks
    rca: str                # root cause analysis
    confidence: str         # High/Medium/Low
    commands: List[str]     # kubectl/terraform commands
    retry_count: int        # for self-correction loop
    pod_name: str           # Kubernetes pod name from cluster scan
    namespace: str          # Kubernetes namespace from cluster scan
    containers: List[str]   # containers related to the incident
    status_reason: str      # Kubernetes status/waiting/terminated reason
    diagnostics: List[str]  # structured pod status/event details
    logs: List[str]         # recent/previous container logs
    log_evidence: str       # concise extracted signal from logs
    logs_used: bool         # whether logs were available to the LLM
    log_attempted: bool     # whether the graph already tried fetching logs
    log_fetch_error: str    # reason logs could not be fetched, if any
