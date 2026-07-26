# Missing Config or File Troubleshooting

## Symptoms
Application logs show no such file or directory, file not found, cannot open config, missing config, failed to load, or module not found.

## Root Cause
The container started without a required file, config, module, or mounted volume. Common causes are wrong image contents, bad command or args, missing ConfigMap or Secret mount, wrong mountPath, typo in file path, or a build/deployment mismatch.

## Resolution Steps
1. Identify the missing path or module from the logs.
2. Inspect the pod command, args, environment, and mounts:
   kubectl describe pod <pod-name> -n <namespace>
3. Check ConfigMap and Secret references:
   kubectl get configmap <configmap-name> -n <namespace> -o yaml
   kubectl get secret <secret-name> -n <namespace>
4. Verify the file exists inside the running container if possible:
   kubectl exec -n <namespace> <pod-name> -- ls -la <path>
5. Check the image tag and deployment spec:
   kubectl get deployment <deployment-name> -n <namespace> -o yaml
6. Fix the image, mount path, ConfigMap, Secret, command, or args, then restart the workload:
   kubectl rollout restart deployment <deployment-name> -n <namespace>
