# Permission and Authentication Failure Troubleshooting

## Symptoms
Application logs show permission denied, unauthorized, forbidden, 401, 403, access denied, invalid credentials, token expired, or RBAC forbidden.

## Root Cause
The application does not have the required credentials or permissions. Common causes are missing or invalid Secrets, wrong environment variables, expired tokens, incorrect ServiceAccount, missing RoleBinding, filesystem permission issues, or external service authorization failure.

## Resolution Steps
1. Identify the denied resource or service from the logs.
2. Check mounted Secrets and environment variables:
   kubectl describe pod <pod-name> -n <namespace>
   kubectl get secret <secret-name> -n <namespace>
3. Verify the ServiceAccount used by the pod:
   kubectl get pod <pod-name> -n <namespace> -o jsonpath="{.spec.serviceAccountName}"
4. Check Kubernetes RBAC permissions:
   kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<namespace>:<serviceaccount>
5. For filesystem permission errors, inspect volume mounts and security context:
   kubectl describe pod <pod-name> -n <namespace>
6. Update the Secret, ServiceAccount, RoleBinding, external credentials, or file permissions, then restart the workload:
   kubectl rollout restart deployment <deployment-name> -n <namespace>
