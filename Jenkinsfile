pipeline {
    agent any

    environment {
        VENV = "${WORKSPACE}@tmp/agent-workflow-venv"
        PATH = "${WORKSPACE}@tmp/agent-workflow-venv/bin:${env.PATH}"
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
                    rm -rf "$WORKSPACE/.jenkins-venv" "$WORKSPACE/.jenkins-local-venv"
                    rm -rf "$VENV"
                    python3 -m venv "$VENV"
                    "$VENV/bin/python" -m pip install \
                        --disable-pip-version-check \
                        --editable '.[dev]'
                '''
            }
        }
        stage('Test and release checks') {
            steps {
                withEnv(['PIP_IGNORE_INSTALLED=1']) {
                    sh './scripts/release-check.sh'
                }
            }
        }
        stage('Build') {
            steps {
                    sh 'python -m build --wheel --no-isolation'
            }
        }
        stage('Host install') {
            steps {
                sh '''
                    set -eu
                    target_user="${AGENT_WORKFLOW_HOST_INSTALL_USER:-}"
                    if [ -z "$target_user" ]; then
                        echo 'AGENT_WORKFLOW_HOST_INSTALL_USER must name the host account to update' >&2
                        exit 2
                    fi
                    host_python="${AGENT_WORKFLOW_HOST_PYTHON:-/usr/bin/python3}"
                    test -x "$host_python" || {
                        echo "host Python interpreter is not executable: $host_python" >&2
                        exit 2
                    }
                    wheel="$(find "$WORKSPACE/dist" -maxdepth 1 -type f -name 'agent_workflow-*.whl' -print -quit)"
                    test -n "$wheel" || {
                        echo 'built agent-workflow wheel is missing' >&2
                        exit 2
                    }
                    install_root="${AGENT_WORKFLOW_HOST_INSTALL_ROOT:-/lump/apps/agent-workflow}"
                    test -x "$install_root/install.sh" || {
                        echo "host install root is invalid: $install_root" >&2
                        exit 2
                    }
                    if [ "$(id -un)" = "$target_user" ]; then
                        AGENT_WORKFLOW_INSTALL_PYTHON="$host_python" "$install_root/install.sh" --wheel "$wheel" --extras mcp
                    else
                        command -v sudo >/dev/null || {
                            echo 'sudo is required when Jenkins deploys to another host account' >&2
                            exit 2
                        }
                        sudo -n -u "$target_user" -H env AGENT_WORKFLOW_INSTALL_PYTHON="$host_python" "$install_root/install.sh" --wheel "$wheel" --extras mcp
                    fi
                '''
            }
        }
    }
}
