# CrashLoopBackOff Troubleshooting

## Symptoms
Pod status shows CrashLoopBackOff, container repeatedly starts and crashes.

## Root Cause
The application inside the container is exiting immediately due to a configuration error, missing dependency, failed health check, or application-level bug.

## Resolution Steps
1. Check logs from the crashing container:
   kubectl logs <pod-name> -n <namespace> --previous
2. Describe the pod for event details:
   kubectl describe pod <pod-name> -n <namespace>
3. Check for misconfigured environment variables or ConfigMaps:
   kubectl get configmap <configmap-name> -n <namespace> -o yaml
4. If the issue is a bad image or command, fix the deployment:
   kubectl edit deployment <deployment-name> -n <namespace>
5. Restart the pod after fixing:
   kubectl rollout restart deployment <deployment-name> -n <namespace>