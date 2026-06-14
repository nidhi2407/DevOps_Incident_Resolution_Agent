# ImagePullBackOff / ErrImagePull Troubleshooting

## Symptoms
Pod status shows ImagePullBackOff or ErrImagePull, container fails to start.

## Root Cause
Kubernetes cannot pull the container image — usually due to an incorrect image name/tag, missing registry credentials, or private registry access issues.

## Resolution Steps
1. Check the exact error:
   kubectl describe pod <pod-name> -n <namespace>
2. Verify the image name and tag are correct in the deployment:
   kubectl get deployment <deployment-name> -n <namespace> -o yaml
3. If using a private registry, verify the imagePullSecret exists:
   kubectl get secret <secret-name> -n <namespace>
4. Create the secret if missing:
   kubectl create secret docker-registry <secret-name> \
     --docker-server=<registry-url> \
     --docker-username=<user> \
     --docker-password=<password> \
     -n <namespace>
5. Reference the secret in the deployment's imagePullSecrets field and reapply:
   kubectl apply -f deployment.yaml