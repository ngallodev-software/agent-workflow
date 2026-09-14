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
                    sh 'python scripts/bump-version.py --check && ./scripts/release-check.sh'
                }
            }
        }
        stage('Benchmark contract smoke') {
            steps {
                sh 'python -m pytest -q tests/invariants/test_benchmark_target_and_tool_mode.py'
            }
        }
        stage('Build') {
            steps {
                sh '''
                    set -eu
                    rm -rf build dist
                    python -m build --sdist --wheel --no-isolation
                    wheel="$(find "$WORKSPACE/dist" -maxdepth 1 -type f -name 'agent_workflow-*.whl' -print -quit)"
                    sdist="$(find "$WORKSPACE/dist" -maxdepth 1 -type f -name 'agent_workflow-*.tar.gz' -print -quit)"
                    test -n "$wheel" || { echo 'built agent-workflow wheel is missing' >&2; exit 2; }
                    test -n "$sdist" || { echo 'built agent-workflow sdist is missing' >&2; exit 2; }
                    python scripts/build-release-bundles.py \
                        --version "v$(tr -d '\n' < VERSION)" \
                        --wheel "$wheel" \
                        --sdist "$sdist" \
                        --output-dir "$WORKSPACE/dist"
                    linux_installer="$WORKSPACE/dist/agent-workflow-$(tr -d '\n' < VERSION)-linux.tar.gz"
                    test -s "$linux_installer" || {
                        echo "Linux installer bundle is missing: $linux_installer" >&2
                        exit 2
                    }
                    echo "Linux installer: $linux_installer"
                '''
            }
        }
    }
}
