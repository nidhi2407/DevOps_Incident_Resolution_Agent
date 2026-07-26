# HTTP 5xx and Upstream Failure Troubleshooting

## Symptoms
Application, ingress, or proxy logs show HTTP 500, 502, 503, 504, upstream failure, bad gateway, service unavailable, gateway timeout, or upstream timed out.

## Root Cause
The request reached the application path, but an application or upstream dependency failed. Common causes are crashed backend pods, no ready endpoints, slow dependencies, bad ingress/service routing, application exceptions, or resource exhaustion.

## Resolution Steps
1. Check application logs for the exact HTTP status and exception:
   kubectl logs <pod-name> -n <namespace> --tail=100
2. Check backend pod readiness:
   kubectl get pods -n <namespace> -o wide
3. Verify the Service and endpoints:
   kubectl get svc <service-name> -n <namespace>
   kubectl get endpoints <service-name> -n <namespace>
4. If ingress is involved, inspect ingress rules and controller logs:
   kubectl describe ingress <ingress-name> -n <namespace>
   kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=100
5. Check dependency health, latency, and resource usage:
   kubectl top pods -n <namespace>
6. Fix the failing backend, route, timeout, or dependency configuration, then restart the affected deployment:
   kubectl rollout restart deployment <deployment-name> -n <namespace>
