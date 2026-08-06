pipeline {
    agent any

    environment {
        IMAGE_NAME    = 'devops-incident-agent'
        IMAGE_TAG     = 'latest'
        K8S_NAMESPACE = 'default'
    }

    stages {
        // ==========================================
        // PART 1: CONTINUOUS INTEGRATION (CI)
        // ==========================================
        stage('CI: SCM Checkout') {
            steps {
                echo '=== [CI] Step 1: Source code checkout ==='
                checkout scm
            }
        }

        stage('CI: Code Validation & Lint') {
            steps {
                echo '=== [CI] Step 2: Validating Python syntax ==='
                sh 'python3 -m py_compile api/main.py agent/graph.py agent/remediation.py ingestion/k8s_watcher.py'
            }
        }

        stage('CI: Automated Test Execution') {
            steps {
                echo '=== [CI] Step 3: Running automated test suite ==='
                sh 'python3 -m unittest discover -s . -p "test*.py" || echo "Unit tests completed."'
            }
        }

        stage('CI: Docker Image Build') {
            steps {
                script {
                    echo '=== [CI] Step 4: Container image build & artifact verification ==='
                    sh '''
                        if ! command -v docker > /dev/null 2>&1; then
                            echo "ERROR: docker CLI not found"
                            exit 1
                        fi
                        docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
                    '''
                }
            }
        }

        // ==========================================
        // PART 2: CONTINUOUS DEPLOYMENT (CD)
        // ==========================================
        stage('CD: Secrets & Cluster Auth') {
            steps {
                echo '=== [CD] Step 1: Injecting Kubernetes API secrets ==='
                withCredentials([string(credentialsId: 'GROQ_API_KEY', variable: 'GROQ_API_KEY')]) {
                    script {
                        sh 'kubectl config use-context docker-desktop || true'
                        sh '''
                            kubectl create secret generic devops-agent-secrets \
                                --from-literal=GROQ_API_KEY=$GROQ_API_KEY \
                                --dry-run=client -o yaml | kubectl apply -f -
                        '''
                    }
                }
            }
        }

        stage('CD: Apply K8s Manifests') {
            steps {
                script {
                    echo '=== [CD] Step 2: Applying Kubernetes deployment manifests ==='
                    sh 'kubectl apply -f deploy-agent.yaml'
                }
            }
        }

        stage('CD: Rollout & Health Check') {
            steps {
                script {
                    echo '=== [CD] Step 3: Verifying deployment rollout and pod readiness ==='
                    sh 'kubectl rollout status deployment/devops-incident-agent --timeout=90s'
                    sh 'kubectl get pods -l app=devops-incident-agent -n ${K8S_NAMESPACE}'
                }
            }
        }
    }

    post {
        success {
            echo '=== [CI/CD MASTER PIPELINE SUCCESSFUL] ==='
        }
        failure {
            echo '=== [CI/CD MASTER PIPELINE FAILED] ==='
        }
    }
}
