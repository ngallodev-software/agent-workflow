pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 20, unit: 'MINUTES')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Test and release checks') {
            steps {
                sh './scripts/release-check.sh'
            }
        }
        stage('Build') {
            steps {
                sh 'python3 -m build --wheel --no-isolation'
            }
        }
        stage('Local install') {
            steps {
                sh './scripts/jenkins-local-install.sh'
            }
        }
    }
}
