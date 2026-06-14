# PVC Pending Troubleshooting

## Symptoms
PersistentVolumeClaim (PVC) remains in Pending status, dependent pods stuck in ContainerCreating.

## Root Cause
No PersistentVolume matches the PVC's requested storage class, size, or access mode, or the storage provisioner is failing.

## Resolution Steps
1. Check PVC status and events:
   kubectl describe pvc <pvc-name> -n <namespace>
2. List available storage classes:
   kubectl get storageclass
3. Verify the PVC's storageClassName matches an existing StorageClass:
   kubectl get pvc <pvc-name> -n <namespace> -o yaml
4. Check the provisioner logs (e.g., for dynamic provisioning issues):
   kubectl logs -n kube-system -l app=<provisioner-name>
5. If no dynamic provisioner exists, manually create a matching PersistentVolume:
   kubectl apply -f pv.yaml
6. Reapply the PVC if edited:
   kubectl apply -f pvc.yaml