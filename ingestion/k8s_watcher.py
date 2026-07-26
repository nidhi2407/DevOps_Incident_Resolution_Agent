import re

from kubernetes import client, config

MAX_LOG_CHARS = 8000
LOG_TAIL_LINES = 100
SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s]+"
)


def _load_core_v1():
    config.load_kube_config()
    return client.CoreV1Api()


def _truncate(text, limit=MAX_LOG_CHARS):
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[-limit:]


def _redact(text):
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", text)


def get_pod_logs(namespace, pod_name, containers=None):
    v1 = _load_core_v1()
    logs = []
    errors = []

    for container in containers or [None]:
        label = container or "default"
        for previous in (True, False):
            try:
                text = v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    container=container,
                    previous=previous,
                    tail_lines=LOG_TAIL_LINES,
                    timestamps=True,
                )
            except Exception as exc:
                errors.append(
                    f"{label} previous={previous}: {exc.__class__.__name__}: {exc}"
                )
                continue

            text = _truncate(_redact(text.strip()))
            if text:
                source = "previous" if previous else "current"
                logs.append(f"[{source} logs: container={label}]\n{text}")

    return logs, errors


def get_unhealthy_pods():
    v1 = _load_core_v1()
    pods = v1.list_pod_for_all_namespaces()

    incidents = []
    for pod in pods.items:
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        phase = pod.status.phase
        statuses = pod.status.container_statuses or []

        issues = []
        containers = []
        reasons = []

        if phase == "Pending" and not statuses:
            conditions = pod.status.conditions or []
            reason = conditions[0].reason if conditions else "Unknown"
            message = conditions[0].message if conditions else "No scheduling info available"
            reasons.append(reason)
            issues.append(f"Pod is Pending. Reason: {reason}. Message: {message}")

        for status in statuses:
            if status.ready:
                continue

            containers.append(status.name)
            waiting = status.state.waiting
            terminated = status.state.terminated

            if waiting:
                reasons.append(waiting.reason or "Unknown")
                issues.append(
                    f"Container '{status.name}' waiting. Reason: {waiting.reason}. "
                    f"Message: {waiting.message or 'N/A'}"
                )
            elif terminated and terminated.exit_code != 0:
                reasons.append(terminated.reason or "Unknown")
                issues.append(
                    f"Container '{status.name}' terminated. Reason: {terminated.reason}. "
                    f"Exit code: {terminated.exit_code}. Message: {terminated.message or 'N/A'}"
                )

            if status.restart_count and status.restart_count > 2:
                issues.append(
                    f"Container '{status.name}' has restarted {status.restart_count} times."
                )

        if issues:
            alert_text = (
                f"Pod {pod_name} in namespace {namespace} is unhealthy.\n"
                + "\n".join(issues)
            )
            incidents.append({
                "alert": alert_text,
                "pod_name": pod_name,
                "namespace": namespace,
                "containers": containers,
                "status_reason": ", ".join(sorted(set(reasons))) or phase,
                "diagnostics": issues,
                "logs": [],
                "logs_used": False,
                "log_attempted": False,
                "log_fetch_error": "",
            })

    return incidents


if __name__ == "__main__":
    incidents = get_unhealthy_pods()
    if incidents:
        for incident in incidents:
            print(incident["alert"])
            print("-" * 60)
    else:
        print("No unhealthy pods detected.")
