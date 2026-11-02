
pipeline {
    agent any

    options {
        disableConcurrentBuilds()
    }

    environment {
        IMAGE_NAME = 'tejas85852/person-registration-app'
        NAMESPACE = 'person-registration'
        RELEASE_NAME = 'person-registration'
        CHART_PATH = './person-registration'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm

                script {
                    env.IMAGE_TAG = sh(
                        script: 'git rev-parse --short=12 HEAD',
                        returnStdout: true
                    ).trim()
                }

                echo "Building image: ${IMAGE_NAME}:${IMAGE_TAG}"
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build \
                      -t ${IMAGE_NAME}:${IMAGE_TAG} .
                '''
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DOCKERHUB_USERNAME',
                        passwordVariable: 'DOCKERHUB_TOKEN'
                    )
                ]) {
                    sh '''
                        set -e

                        echo "$DOCKERHUB_TOKEN" | docker login \
                          -u "$DOCKERHUB_USERNAME" --password-stdin

                        docker push ${IMAGE_NAME}:${IMAGE_TAG}

                        docker logout
                    '''
                }
            }
        }

        stage('Validate Helm Chart') {
            steps {
                sh '''
                    helm lint ${CHART_PATH}
                '''
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    helm upgrade --install ${RELEASE_NAME} ${CHART_PATH} \
                      --namespace ${NAMESPACE} \
                      --set-string app.image.tag=${IMAGE_TAG} \
                      --wait \
                      --timeout 5m
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    kubectl rollout status \
                      deployment/person-registration-app \
                      -n ${NAMESPACE} \
                      --timeout=300s

                    kubectl get pods -n ${NAMESPACE}

                    kubectl get deployment person-registration-app \
                      -n ${NAMESPACE}
                '''
            }
        }
    }
}

