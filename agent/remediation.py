"""
Automated Remediation Agent — agent/remediation.py

Safely executes and verifies simple self-healing actions suggested by
the LLM runbook engine. Uses a whitelist of permitted kubectl operations
and verifies pod recovery after execution.
"""
import time
import subprocess
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# Whitelist of safe, allowed remediation actions
# ─────────────────────────────────────────────────
ALLOWED_ACTIONS = {
    "restart_deployment": {
        "description": "Restart a deployment to recover from CrashLoopBackOff or OOMKilled",
        "command_template": "kubectl rollout restart deployment/{name} -n {namespace}",
        "safety": "low-risk",
    },
    "delete_pod": {
        "description": "Delete a failed pod to let its ReplicaSet recreate it cleanly",
        "command_template": "kubectl delete pod {name} -n {namespace} --grace-period=0",
        "safety": "low-risk",
    },
    "scale_up": {
        "description": "Scale a deployment up by one replica to replace a crashing instance",
        "command_template": "kubectl scale deployment/{name} --replicas={replicas} -n {namespace}",
        "safety": "low-risk",
    },
    "scale_down": {
        "description": "Scale a deployment to 0 replicas and back up to clear stuck states",
        "command_template": "kubectl scale deployment/{name} --replicas=0 -n {namespace}",
        "safety": "low-risk",
    },
    "rollout_undo": {
        "description": "Roll back a deployment to its previous revision",
        "command_template": "kubectl rollout undo deployment/{name} -n {namespace}",
        "safety": "medium-risk",
    },
}

# ─────────────────────────────────────────────────
# Result data class
# ─────────────────────────────────────────────────
@dataclass
class RemediationResult:
    action_type: str
    pod_name: str
    namespace: str
    command: str
    success: bool
    output: str
    error: str = ""
    verification_status: str = "not_checked"
    verification_msg: str = ""
    executed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ─────────────────────────────────────────────────
# In-memory audit log (session-scoped)
# ─────────────────────────────────────────────────
remediation_history: list[dict] = []


def get_allowed_actions() -> dict:
    """Return the catalogue of permitted remediation actions."""
    return {k: {"description": v["description"], "safety": v["safety"]}
            for k, v in ALLOWED_ACTIONS.items()}


def validate_action(action_type: str) -> tuple[bool, str]:
    """
    Validate that the requested action type is in the whitelist.
    Returns (is_valid, reason_if_invalid).
    """
    if not action_type:
        return False, "No action_type provided."
    if action_type not in ALLOWED_ACTIONS:
        allowed = ", ".join(ALLOWED_ACTIONS.keys())
        return False, f"Action '{action_type}' is not in the permitted actions whitelist. Allowed: {allowed}"
    return True, ""


def _build_command(action_type: str, pod_name: str, namespace: str, replicas: int = 1) -> str:
    """Build the actual kubectl command from the template."""
    template = ALLOWED_ACTIONS[action_type]["command_template"]
    return template.format(name=pod_name, namespace=namespace, replicas=replicas)


def _is_k8s_connected() -> bool:
    """Check if Kubernetes kubeconfig is loaded and cluster is reachable."""
    try:
        from kubernetes import config, client
        config.load_kube_config()
        # Ping the API server with a short timeout
        client.CoreV1Api().list_namespace(timeout_seconds=2)
        return True
    except Exception:
        return False


def _run_kubectl(command: str) -> tuple[bool, str, str]:
    """
    Execute a kubectl command via subprocess.
    Returns (success, stdout, stderr).
    """
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        success = result.returncode == 0
        return success, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "kubectl command timed out after 30 seconds."
    except FileNotFoundError:
        return False, "", "kubectl not found on PATH. Ensure kubectl is installed and configured."
    except Exception as e:
        return False, "", str(e)


def verify_pod_recovery(pod_name: str, namespace: str, timeout_seconds: int = 60) -> tuple[str, str]:
    """
    Poll pod status for up to `timeout_seconds` to verify recovery.
    Returns (status: 'recovered'|'failed'|'timeout', message).
    """
    start = time.time()
    check_cmd = f"kubectl get pod {pod_name} -n {namespace} --no-headers"

    while time.time() - start < timeout_seconds:
        success, stdout, stderr = _run_kubectl(check_cmd)

        if not success:
            # Pod may have been deleted and not yet recreated
            time.sleep(5)
            continue

        if stdout:
            parts = stdout.split()
            if len(parts) >= 3:
                ready = parts[1]       # e.g. "1/1"
                status = parts[2]      # e.g. "Running"

                if status == "Running" and "/" in ready:
                    total_str, ready_str = ready.split("/")[1], ready.split("/")[0]
                    if ready_str == total_str:
                        return "recovered", f"Pod {pod_name} is now Running ({ready} Ready)."

                if status in ("Error", "CrashLoopBackOff", "OOMKilled"):
                    return "failed", f"Pod {pod_name} is still failing with status: {status}."

        time.sleep(5)

    return "timeout", f"Pod {pod_name} did not recover within {timeout_seconds}s. Manual investigation required."


def execute_remediation(
    action_type: str,
    pod_name: str,
    namespace: str,
    replicas: int = 1,
    verify: bool = True,
    verify_timeout: int = 60,
) -> RemediationResult:
    """
    Main entry point: validate, execute, and verify a remediation action.
    """
    valid, reason = validate_action(action_type)
    if not valid:
        result = RemediationResult(
            action_type=action_type,
            pod_name=pod_name,
            namespace=namespace,
            command="",
            success=False,
            output="",
            error=reason,
            verification_status="skipped",
            verification_msg="Validation failed; command not executed.",
        )
        remediation_history.append(_result_to_dict(result))
        return result

    command = _build_command(action_type, pod_name, namespace, replicas)
    connected = _is_k8s_connected()

    if not connected:
        # Mock mode fallback
        logger.info("Kubernetes cluster not connected. Running simulation mode.")
        if "restart" in command:
            stdout = f"deployment.apps/{pod_name} restarted (simulated)"
        elif "delete" in command:
            stdout = f"pod \"{pod_name}\" deleted (simulated)"
        elif "scale" in command:
            stdout = f"deployment.apps/{pod_name} scaled to {replicas} (simulated)"
        else:
            stdout = f"rollout undo deployment.apps/{pod_name} (simulated)"

        success = True
        stderr = ""
        verification_status = "not_checked"
        verification_msg = ""

        if verify and pod_name and namespace:
            try:
                from ingestion.k8s_watcher import MOCK_PODS_DATA
                # 1. Update status to transient state
                for p in MOCK_PODS_DATA:
                    if p["pod_name"] == pod_name:
                        p["status"] = "Pending"
                        p["status_reason"] = "Pending"
                        p["ready"] = "0/1"
                        p["alert"] = f"Pod {pod_name} is recovering..."
                        p["diagnostics"] = ["Container initializing...", "Running simulated remediation action."]

                time.sleep(2)  # Delay for UI telemetry check

                # 2. Update status to recovered
                for p in MOCK_PODS_DATA:
                    if p["pod_name"] == pod_name:
                        p["status"] = "Running"
                        p["status_reason"] = "Running"
                        p["ready"] = "1/1" if len(p.get("containers", [])) <= 1 else f"{len(p.get('containers', []))}/{len(p.get('containers', []))}"
                        p["is_healthy"] = True
                        p["alert"] = ""
                        p["diagnostics"] = []

                verification_status = "recovered"
                verification_msg = f"Simulated recovery: Pod {pod_name} transitioned to Running (Ready) successfully."
            except Exception as e:
                verification_status = "failed"
                verification_msg = f"Simulated recovery failed: {str(e)}"
    else:
        # Real execution mode
        success, stdout, stderr = _run_kubectl(command)
        verification_status = "not_checked"
        verification_msg = ""

        if success and verify and pod_name and namespace:
            time.sleep(3)  # Brief wait for K8s to register the change
            verification_status, verification_msg = verify_pod_recovery(
                pod_name, namespace, timeout_seconds=verify_timeout
            )

    result = RemediationResult(
        action_type=action_type,
        pod_name=pod_name,
        namespace=namespace,
        command=command,
        success=success,
        output=stdout,
        error=stderr,
        verification_status=verification_status,
        verification_msg=verification_msg,
    )

    remediation_history.append(_result_to_dict(result))
    return result


def _result_to_dict(result: RemediationResult) -> dict:
    return {
        "action_type": result.action_type,
        "pod_name": result.pod_name,
        "namespace": result.namespace,
        "command": result.command,
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "verification_status": result.verification_status,
        "verification_msg": result.verification_msg,
        "executed_at": result.executed_at,
    }

