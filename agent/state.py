from typing import TypedDict, List

class AgentState(TypedDict):
    alert: str              # raw incoming alert
    context: List[str]      # retrieved runbook chunks
    rca: str                # root cause analysis
    confidence: str         # High/Medium/Low
    commands: List[str]     # kubectl/terraform commands
    retry_count: int        # for self-correction loop