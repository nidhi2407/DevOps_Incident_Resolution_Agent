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
                // Pull the Groq API key from Jenkins credentials (ID: GROQ_API_KEY)
                withCredentials([string(credentialsId: 'GROQ_API_KEY', variable: 'GROQ_API_KEY')]) {
                    script {
                        // Verify kubectl is present inside the container
                        sh '''
                            if ! command -v kubectl >/dev/null 2>&1; then
                                echo "ERROR: kubectl not installed in Jenkins container"
                                exit 1
                            fi
                        '''
                        // Create or replace the secret safely – the variable is expanded by the shell, not Groovy
                        sh "kubectl create secret generic devops-agent-secrets --from-literal=GROQ_API_KEY=${GROQ_API_KEY} --dry-run=client -o yaml | kubectl apply -f -"
                    }
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
