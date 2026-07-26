pipeline {
    agent any

    environment {
        // Reference the secret text credential set in Jenkins with ID 'GROQ_API_KEY'
        GROQ_API_KEY = credentials('GROQ_API_KEY')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Secrets') {
            steps {
                script {
                    echo "Setting up Kubernetes Secrets..."
                    sh """
                    kubectl get secret devops-agent-secrets >/dev/null 2>&1 || \
                    kubectl create secret generic devops-agent-secrets --from-literal=GROQ_API_KEY="${GROQ_API_KEY}"
                    """
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "Building Docker image inside Minikube's daemon..."
                    // Point Docker to Minikube's daemon and build the image
                    sh """
                    eval \$(minikube -p minikube docker-env)
                    docker build -t devops-incident-agent:latest .
                    """
                }
            }
        }

        stage('Deploy') {
            steps {
                script {
                    echo "Deploying application to Minikube..."
                    sh "kubectl apply -f deploy-agent.yaml"
                }
            }
        }

        stage('Verify') {
            steps {
                script {
                    echo "Verifying deployment health..."
                    sh "kubectl rollout status deployment/devops-incident-agent --timeout=90s"
                    sh "kubectl get pods -l app=devops-incident-agent"
                }
            }
        }
    }
}
