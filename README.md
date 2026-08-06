# DevOps Incident Resolution Agent

Autonomous AIOps Root Cause Analysis & Self-Healing Pipeline for Kubernetes Infrastructure.

## 🚀 Segregated CI/CD Pipeline Architecture

The project features a clean separation between Continuous Integration (CI) and Continuous Deployment (CD) pipelines in Jenkins:

### 1. Continuous Integration (CI) Pipeline (`Jenkinsfile.ci`)
- **Stage 1: SCM Checkout**: Pulls latest source code.
- **Stage 2: Syntax & Lint Validation**: Compiles Python code (`py_compile`) to verify syntax integrity across API and Agent modules.
- **Stage 3: Automated Unit Testing**: Runs test suite (`unittest`).
- **Stage 4: Docker Image Build**: Builds container image (`devops-incident-agent:latest`) and validates build artifacts.

### 2. Continuous Deployment (CD) Pipeline (`Jenkinsfile.cd`)
- **Stage 1: Manifests Checkout**: Pulls deployment configuration.
- **Stage 2: Cluster Credentials & Secrets**: Injects `GROQ_API_KEY` into Kubernetes Secret (`devops-agent-secrets`).
- **Stage 3: K8s Deployment**: Applies `deploy-agent.yaml` manifests.
- **Stage 4: Rollout Verification**: Polls `kubectl rollout status` ensuring 1/1 container readiness.
- **Stage 5: Smoke Test**: Pings NodePort endpoint (`http://localhost:30800/pods`) for 200 OK health.

---

## 🛠️ Quick Commands

```bash
# Run local API server
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Deploy to Kubernetes
kubectl apply -f deploy-agent.yaml

# Test UI Endpoint
http://localhost:30800
```
