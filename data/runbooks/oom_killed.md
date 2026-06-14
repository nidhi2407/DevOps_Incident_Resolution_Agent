# OOMKilled Pod Troubleshooting

## Symptoms
Pod status shows OOMKilled, container exits with code 137.

## Root Cause
Container memory usage exceeded the limit set in resources.limits.memory.

## Resolution Steps
1. Check current memory limits: kubectl describe pod <pod-name>
2. Increase memory limit in deployment yaml:
   resources:
     limits:
       memory: "512Mi"
3. Apply: kubectl apply -f deployment.yaml
4. Monitor: kubectl top pod <pod-name>