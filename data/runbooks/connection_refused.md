# Connection Refused Troubleshooting

## Symptoms
Application logs show connection refused, ECONNREFUSED, dial tcp connection refused, failed to connect, or upstream connect error.

## Root Cause
The application reached the target host, but nothing accepted the connection on the target port. Common causes are a dependency not running, wrong port, Service selector mismatch, no ready endpoints, container not listening, or network policy blocking the traffic.

## Resolution Steps
1. Identify the host and port from the logs.
2. Check whether the Kubernetes Service exists:
   kubectl get svc <service-name> -n <namespace>
3. Check whether the Service has endpoints:
   kubectl get endpoints <service-name> -n <namespace>
4. Check the dependency pods and readiness:
   kubectl get pods -n <namespace> -l <selector>
   kubectl describe pod <dependency-pod> -n <namespace>
5. Verify the container is listening on the expected port:
   kubectl exec -n <namespace> <dependency-pod> -- netstat -tuln
6. Fix the Service port, targetPort, selector, application configuration, or dependency deployment, then restart affected workloads:
   kubectl rollout restart deployment <deployment-name> -n <namespace>
