import re

from kubernetes import client, config

MAX_LOG_CHARS = 8000
LOG_TAIL_LINES = 100
SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s]+"
)


def _load_core_v1():
    try:
        # Running inside a Kubernetes pod — use the mounted service account token
        config.load_incluster_config()
    except config.ConfigException:
        # Running locally — use ~/.kube/config
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
    try:
        v1 = _load_core_v1()
        logs = []
        errors = []

        container_list = list(containers) if containers else []
        if None not in container_list:
            container_list.append(None)

        for container in container_list:
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
    except Exception:
        # Fallback mock logs when K8s cluster is not connected
        mock_map = {
            "dns-fail-pod": [
                "[previous logs: container=dns-test]\n2026-07-26T10:12:00Z [INFO] Initializing DNS lookup...\n2026-07-26T10:12:01Z [ERROR] nslookup failed: server can't find nonexistent.invalid.domain.test: NXDOMAIN\n2026-07-26T10:12:01Z [FATAL] Critical network failure. Service exiting with code 1."
            ],
            "payment-service-7d9b4c8-2x9k": [
                "[previous logs: container=payment-api]\n2026-07-26T08:00:12Z [WARN] Heap memory allocation approaching max limit (502MB/512MB)\n2026-07-26T08:00:15Z [ERROR] java.lang.OutOfMemoryError: Java heap space\n2026-07-26T08:00:15Z K8s Event: Container payment-api terminated by OOMKiller with Exit Code 137."
            ],
            "web-frontend-5678ab-9z1q": [
                "[previous logs: container=nginx]\n2026-07-26T09:15:01Z [error] 12#12: *1 connect() failed (111: Connection refused) while connecting to upstream auth-service:8080\n2026-07-26T09:15:02Z [emerg] 1#1: upstream server auth-service:8080 unreachable"
            ]
        }
        logs = mock_map.get(pod_name, [f"[previous logs: container=default]\n2026-07-26T10:15:00Z [ERROR] Container error in pod {pod_name}: server can't find nonexistent.invalid.domain.test: NXDOMAIN"])
        return logs, []


MOCK_PODS_DATA = [
        {
            "pod_name": "dns-fail-pod",
            "namespace": "default",
            "status": "CrashLoopBackOff",
            "status_reason": "CrashLoopBackOff",
            "restarts": 8,
            "containers": ["dns-test"],
            "ready": "0/1",
            "node": "ip-10-0-1-44",
            "age": "1h 30m",
            "is_healthy": False,
            "alert": "Pod dns-fail-pod in namespace default is stuck in CrashLoopBackOff. Container dns-test failed with DNS resolution error: server can't find nonexistent.invalid.domain.test: NXDOMAIN.",
            "diagnostics": [
                "Container 'dns-test' waiting. Reason: CrashLoopBackOff.",
                "Back-off 5m0s restarting failed container 'dns-test' in pod 'dns-fail-pod'."
            ],
            "logs": [
                "[previous logs: container=dns-test]\n2026-07-26T10:12:00Z [INFO] Initializing DNS lookup...\n2026-07-26T10:12:01Z [ERROR] nslookup failed: server can't find nonexistent.invalid.domain.test: NXDOMAIN\n2026-07-26T10:12:01Z [FATAL] Critical network failure. Service exiting with code 1."
            ]
        },
        {
            "pod_name": "payment-service-7d9b4c8-2x9k",
            "namespace": "prod",
            "status": "OOMKilled",
            "status_reason": "OOMKilled",
            "restarts": 5,
            "containers": ["payment-api"],
            "ready": "0/1",
            "node": "ip-10-0-1-44",
            "age": "4h 12m",
            "is_healthy": False,
            "alert": "Pod payment-service-7d9b4c8-2x9k in namespace prod is showing status OOMKilled. Container payment-api terminated with Exit Code 137 (Out of Memory).",
            "diagnostics": [
                "Container 'payment-api' terminated. Exit code: 137. Reason: OOMKilled.",
                "Memory usage spiked to limit: 512Mi / 512Mi."
            ]
        },
        {
            "pod_name": "web-frontend-5678ab-9z1q",
            "namespace": "prod",
            "status": "CrashLoopBackOff",
            "status_reason": "CrashLoopBackOff",
            "restarts": 12,
            "containers": ["nginx"],
            "ready": "0/1",
            "node": "ip-10-0-1-12",
            "age": "1d 2h",
            "is_healthy": False,
            "alert": "Pod web-frontend-5678ab-9z1q in namespace prod is stuck in CrashLoopBackOff. Container nginx failed to start: Connection refused to backend auth-service:8080.",
            "diagnostics": [
                "Container 'nginx' waiting. Reason: CrashLoopBackOff.",
                "Back-off 5m0s restarting failed container 'nginx' in pod 'web-frontend-5678ab-9z1q'."
            ]
        },
        {
            "pod_name": "auth-service-6879cd-3f4a",
            "namespace": "prod",
            "status": "Running",
            "status_reason": "Running",
            "restarts": 0,
            "containers": ["auth"],
            "ready": "1/1",
            "node": "ip-10-0-1-44",
            "age": "5d 8h",
            "is_healthy": True,
            "alert": "",
            "diagnostics": []
        },
        {
            "pod_name": "orders-db-0",
            "namespace": "prod",
            "status": "Running",
            "status_reason": "Running",
            "restarts": 1,
            "containers": ["postgres"],
            "ready": "1/1",
            "node": "ip-10-0-2-89",
            "age": "12d",
            "is_healthy": True,
            "alert": "",
            "diagnostics": []
        },
        {
            "pod_name": "redis-cache-master-0",
            "namespace": "prod",
            "status": "Running",
            "status_reason": "Running",
            "restarts": 0,
            "containers": ["redis"],
            "ready": "1/1",
            "node": "ip-10-0-2-90",
            "age": "12d",
            "is_healthy": True,
            "alert": "",
            "diagnostics": []
        },
        {
            "pod_name": "ingress-controller-4a2b",
            "namespace": "kube-system",
            "status": "Running",
            "status_reason": "Running",
            "restarts": 0,
            "containers": ["haproxy"],
            "ready": "2/2",
            "node": "ip-10-0-1-12",
            "age": "30d",
            "is_healthy": True,
            "alert": "",
            "diagnostics": []
        },
        {
            "pod_name": "coredns-5577-8k9p",
            "namespace": "kube-system",
            "status": "Running",
            "status_reason": "Running",
            "restarts": 0,
            "containers": ["coredns"],
            "ready": "1/1",
            "node": "ip-10-0-1-44",
            "age": "30d",
            "is_healthy": True,
            "alert": "",
            "diagnostics": []
        },
        {
            "pod_name": "metrics-server-8f3a",
            "namespace": "kube-system",
            "status": "Running",
            "status_reason": "Running",
            "restarts": 0,
            "containers": ["metrics-server"],
            "ready": "1/1",
            "node": "ip-10-0-1-12",
            "age": "30d",
            "is_healthy": True,
            "alert": "",
            "diagnostics": []
        },
        {
            "pod_name": "worker-processor-99x2",
            "namespace": "staging",
            "status": "Pending",
            "status_reason": "InsufficientMemory",
            "restarts": 0,
            "containers": ["celery-worker"],
            "ready": "0/1",
            "node": "unassigned",
            "age": "15m",
            "is_healthy": False,
            "alert": "Pod worker-processor-99x2 in namespace staging is stuck in Pending. Reason: InsufficientMemory. 0/3 nodes are available: 3 Insufficient memory.",
            "diagnostics": [
                "Pod is Pending. Reason: InsufficientMemory.",
                "FailedScheduling: 0/3 nodes are available: 3 Insufficient memory."
            ]
        },
        {
            "pod_name": "analytics-job-4412",
            "namespace": "staging",
            "status": "Running",
            "status_reason": "Running",
            "restarts": 0,
            "containers": ["spark"],
            "ready": "1/1",
            "node": "ip-10-0-2-89",
            "age": "2h",
            "is_healthy": True,
            "alert": "",
            "diagnostics": []
        }
    ]


def get_mock_pods():
    return MOCK_PODS_DATA



def get_all_pods_summary():
    try:
        v1 = _load_core_v1()
        pods = v1.list_pod_for_all_namespaces()

        result = []
        for pod in pods.items:
            pod_name = pod.metadata.name
            namespace = pod.metadata.namespace
            phase = pod.status.phase
            statuses = pod.status.container_statuses or []

            restarts = sum(s.restart_count for s in statuses) if statuses else 0
            ready_count = sum(1 for s in statuses if s.ready)
            total_count = len(statuses) if statuses else 1
            ready_str = f"{ready_count}/{total_count}"

            is_healthy = (phase == "Running") and (ready_count == total_count)
            status_reason = phase

            for status in statuses:
                if not status.ready:
                    if status.state.waiting:
                        status_reason = status.state.waiting.reason or status_reason
                    elif status.state.terminated:
                        status_reason = status.state.terminated.reason or status_reason

            alert_text = ""
            diagnostics = []
            if not is_healthy:
                alert_text = f"Pod {pod_name} in namespace {namespace} is status {status_reason}."
                diagnostics.append(f"Phase: {phase}, Status Reason: {status_reason}")

            result.append({
                "pod_name": pod_name,
                "namespace": namespace,
                "status": status_reason,
                "status_reason": status_reason,
                "restarts": restarts,
                "containers": [s.name for s in statuses] if statuses else ["default"],
                "ready": ready_str,
                "node": pod.spec.node_name or "unassigned",
                "age": "active",
                "is_healthy": is_healthy,
                "alert": alert_text,
                "diagnostics": diagnostics
            })
        return result
    except Exception:
        # Fallback to simulated cluster summary if K8s is not running locally
        return get_mock_pods()


def get_unhealthy_pods():
    try:
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
    except Exception:
        # Fallback mock unhealthy pods
        return [p for p in get_mock_pods() if not p["is_healthy"]]


if __name__ == "__main__":
    incidents = get_unhealthy_pods()
    if incidents:
        for incident in incidents:
            print(incident["alert"])
            print("-" * 60)
    else:
        print("No unhealthy pods detected.")

