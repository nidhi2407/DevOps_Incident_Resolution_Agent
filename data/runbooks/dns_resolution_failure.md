# DNS Resolution Failure Troubleshooting

## Symptoms
Application logs show DNS lookup failures such as NXDOMAIN, server can't find, no such host, Name or service not known, or temporary failure in name resolution.

## Root Cause
The application is trying to resolve a hostname that Kubernetes DNS or the upstream DNS resolver cannot find. Common causes are a typo in the hostname, wrong Kubernetes Service name or namespace, missing Service, broken CoreDNS, or an invalid external domain.

## Resolution Steps
1. Confirm the failing hostname from the logs:
   kubectl logs <pod-name> -n <namespace> --previous
2. Check whether the referenced Kubernetes Service exists:
   kubectl get svc -A | grep <service-name>
3. If the dependency is in another namespace, use the full DNS name:
   <service-name>.<namespace>.svc.cluster.local
4. Test DNS resolution from a debug pod:
   kubectl run dns-debug --rm -it --image=busybox:1.36 -- nslookup <hostname>
5. Check CoreDNS health and logs:
   kubectl get pods -n kube-system -l k8s-app=kube-dns
   kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100
6. Fix the application configuration, ConfigMap, Secret, or environment variable that contains the invalid hostname, then restart the workload:
   kubectl rollout restart deployment <deployment-name> -n <namespace>
