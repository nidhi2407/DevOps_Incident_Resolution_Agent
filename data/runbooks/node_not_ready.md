# Node NotReady Troubleshooting

## Symptoms
A node shows status NotReady in kubectl get nodes, pods on that node may be evicted or stuck.

## Root Cause
The kubelet on the node has stopped reporting status — commonly caused by network issues, resource exhaustion (disk/memory pressure), kubelet crash, or container runtime failure.

## Resolution Steps
1. Check node status and conditions:
   kubectl describe node <node-name>
2. Check disk and memory pressure conditions in the output (DiskPressure, MemoryPressure, PIDPressure).
3. SSH into the node and check kubelet status:
   systemctl status kubelet
4. Restart kubelet if it's stopped:
   systemctl restart kubelet
5. Check container runtime (containerd/docker) status:
   systemctl status containerd
6. If the node remains NotReady, cordon and drain it to reschedule workloads:
   kubectl cordon <node-name>
   kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data