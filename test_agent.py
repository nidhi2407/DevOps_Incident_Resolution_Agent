from agent.graph import agent_graph

test_alerts = [
    "Pod my-app-7f9c6 in namespace prod is showing status OOMKilled",
    "Pod web-server-2x9k is stuck in CrashLoopBackOff",
    "Something is wrong with my cluster"
]

for alert in test_alerts:
    initial_state = {
        "alert": alert,
        "context": [],
        "rca": "",
        "confidence": "",
        "commands": [],
        "retry_count": 0
    }
    result = agent_graph.invoke(initial_state)
    print(f"ALERT: {alert}")
    print(result["rca"])
    print("Confidence:", result["confidence"])
    print("Retry count:", result["retry_count"])
    print("-" * 80)