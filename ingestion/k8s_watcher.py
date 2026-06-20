from kubernetes import client, config

def get_unhealthy_pods():
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pods = v1.list_pod_for_all_namespaces()

    alerts = []
    for pod in pods.items:
        statuses = pod.status.container_statuses or []
        for status in statuses:
            waiting = status.state.waiting
            if waiting and waiting.reason in [
                "CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"
            ]:
                alert_text = (
                    f"Pod {pod.metadata.name} in namespace "
                    f"{pod.metadata.namespace} is showing status {waiting.reason}"
                )
                alerts.append(alert_text)

        # Also catch OOMKilled (shows in last terminated state)
        for status in statuses:
            terminated = status.state.terminated
            if terminated and terminated.reason == "OOMKilled":
                alert_text = (
                    f"Pod {pod.metadata.name} in namespace "
                    f"{pod.metadata.namespace} is showing status OOMKilled"
                )
                alerts.append(alert_text)

    return alerts


if __name__ == "__main__":
    alerts = get_unhealthy_pods()
    if alerts:
        for a in alerts:
            print(a)
    else:
        print("No unhealthy pods detected.")