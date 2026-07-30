from langgraph.graph import END, StateGraph
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from agent.state import AgentState
from agent.prompts import RCA_PROMPT
from dotenv import load_dotenv
import os

os.environ["ANONYMIZED_TELEMETRY"] = "False"

load_dotenv()

embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
vectordb = Chroma(persist_directory="data/chroma_db", embedding_function=embeddings)
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

VAGUE_STATUS_REASONS = {
    "error",
    "unknown",
    "containercreating",
    "runcontainererror",
    "createcontainerconfigerror",
    "crashloopbackoff",
    "oomkilled",
}


def _join(items):
    return "\n\n".join(items or []) or "Not provided."


def _extract_confidence(text):
    upper = (text or "").upper()
    if "CONFIDENCE: HIGH" in upper or "CONFIDENCE:HIGH" in upper:
        return "High"
    if "CONFIDENCE: MEDIUM" in upper or "CONFIDENCE:MEDIUM" in upper:
        return "Medium"
    if "CONFIDENCE: LOW" in upper or "CONFIDENCE:LOW" in upper:
        return "Low"
    return "Medium"  # Default fallback if LLM omitted line


def _extract_log_evidence(logs):
    evidence = []
    for line in "\n".join(logs or []).splitlines():
        lower = line.lower()
        if "nxdomain" in lower:
            evidence.append(line.strip())
        elif "connection refused" in lower:
            evidence.append(line.strip())
        elif "permission denied" in lower:
            evidence.append(line.strip())
        elif "no such file or directory" in lower:
            evidence.append(line.strip())
        elif "oomkilled" in lower:
            evidence.append(line.strip())
        elif "error" in lower and len(line.strip()) < 300:
            evidence.append(line.strip())

        if len(evidence) >= 5:
            break

    return "\n".join(evidence)


def retrieve_node(state: AgentState) -> AgentState:
    docs = vectordb.similarity_search(state["alert"], k=3)
    state["context"] = [d.page_content for d in docs]
    return state


VALID_ACTIONS = {"restart_deployment", "delete_pod", "rollout_undo", "scale_up", "none"}


def _extract_remediation_action(text: str) -> dict:
    """
    Parse the REMEDIATION block from the LLM response.
    Returns {"action": ..., "reason": ...}.
    """
    action = "none"
    reason = ""
    lines = text.splitlines()
    in_remediation = False

    for line in lines:
        stripped = line.strip()
        if stripped == "REMEDIATION:":
            in_remediation = True
            continue
        if in_remediation:
            if stripped.startswith("ACTION:"):
                raw = stripped.replace("ACTION:", "").strip().lower()
                if raw in VALID_ACTIONS:
                    action = raw
            elif stripped.startswith("REASON:"):
                reason = stripped.replace("REASON:", "").strip()

    return {"action": action, "reason": reason}


def analyze_node(state: AgentState) -> AgentState:
    chain = RCA_PROMPT | llm
    response = chain.invoke({
        "context": _join(state.get("context")),
        "diagnostics": _join(state.get("diagnostics")),
        "log_evidence": state.get("log_evidence") or "Not provided.",
        "logs": _join(state.get("logs")),
        "alert": state["alert"],
    })
    text = response.content

    state["rca"] = text
    state["confidence"] = _extract_confidence(text)
    state["remediation_action"] = _extract_remediation_action(text)
    return state


def _status_is_vague(state: AgentState) -> bool:
    reasons = state.get("status_reason", "")
    normalized = {
        reason.strip().lower().replace(" ", "")
        for reason in reasons.split(",")
        if reason.strip()
    }
    return bool(normalized & VAGUE_STATUS_REASONS) or not reasons


def _should_fetch_logs(state: AgentState) -> bool:
    if state.get("log_attempted"):
        return False
    if not state.get("pod_name") or not state.get("namespace"):
        return False
    if not state.get("containers"):
        return False
    return state.get("confidence") != "High" or _status_is_vague(state) or not state.get("logs")



def fetch_logs_node(state: AgentState) -> AgentState:
    from ingestion.k8s_watcher import get_pod_logs

    state["log_attempted"] = True
    logs, errors = get_pod_logs(
        namespace=state["namespace"],
        pod_name=state["pod_name"],
        containers=state.get("containers"),
    )
    state["logs"] = logs
    state["logs_used"] = bool(logs)
    state["log_evidence"] = _extract_log_evidence(logs)
    state["log_fetch_error"] = "\n".join(errors[-5:]) if errors else ""

    if logs:
        state.setdefault("diagnostics", [])
        state["diagnostics"].append(
            f"Fetched {len(logs)} log block(s) from pod {state['pod_name']}."
        )
        if state["log_evidence"]:
            state["diagnostics"].append(
                f"Key log evidence:\n{state['log_evidence']}"
            )
    elif errors:
        state.setdefault("diagnostics", [])
        state["diagnostics"].append(
            "Log collection attempted but no log output was available."
        )

    return state


def route_after_analyze(state: AgentState) -> str:
    if _should_fetch_logs(state):
        return "logs"
    if state.get("confidence") == "Low" and state.get("retry_count", 0) < 2:
        return "retry"
    return "done"


def retry_node(state: AgentState) -> AgentState:
    state["retry_count"] = state.get("retry_count", 0) + 1
    docs = vectordb.similarity_search(state["alert"], k=5)
    state["context"] = [d.page_content for d in docs]
    return state


workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("fetch_logs", fetch_logs_node)
workflow.add_node("retry", retry_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "analyze")
workflow.add_conditional_edges("analyze", route_after_analyze, {
    "logs": "fetch_logs",
    "retry": "retry",
    "done": END,
})
workflow.add_edge("fetch_logs", "analyze")
workflow.add_edge("retry", "analyze")

agent_graph = workflow.compile()
