pipeline {
    agent any

    environment {
        VENV = "${WORKSPACE}/.jenkins-venv"
        PATH = "${WORKSPACE}/.jenkins-venv/bin:${env.PATH}"
    }

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
        stage('Prepare Python environment') {
            steps {
                sh '''
                    rm -rf "$VENV"
                    python3 -m venv "$VENV"
                    "$VENV/bin/python" -m pip install \
                        --disable-pip-version-check \
                        'pytest>=8,<10' \
                        'jsonschema>=4.18,<5' \
                        'build'
                '''
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
