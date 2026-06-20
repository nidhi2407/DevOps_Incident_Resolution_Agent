from kubernetes import client, config

def get_unhealthy_pods():
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pods = v1.list_pod_for_all_namespaces()

    alerts = []
    for pod in pods.items:
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        phase = pod.status.phase
        statuses = pod.status.container_statuses or []

        issues = []

        # Case 1: Pod stuck in Pending (not yet scheduled / no container statuses)
        if phase == "Pending" and not statuses:
            conditions = pod.status.conditions or []
            reason = conditions[0].reason if conditions else "Unknown"
            message = conditions[0].message if conditions else "No scheduling info available"
            issues.append(f"Pod is Pending. Reason: {reason}. Message: {message}")

        # Case 2: Any container not ready/running — capture RAW info, no filtering by known reasons
        for status in statuses:
            if status.ready:
                continue  # healthy container, skip

            waiting = status.state.waiting
            terminated = status.state.terminated

            if waiting:
                issues.append(
                    f"Container '{status.name}' waiting. Reason: {waiting.reason}. "
                    f"Message: {waiting.message or 'N/A'}"
                )
            elif terminated and terminated.exit_code != 0:
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
            alerts.append(alert_text)

    return alerts


if __name__ == "__main__":
    alerts = get_unhealthy_pods()
    if alerts:
        for a in alerts:
            print(a)
            print("-" * 60)
    else:
        print("No unhealthy pods detected.")