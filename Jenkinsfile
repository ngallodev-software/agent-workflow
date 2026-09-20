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
        stage('Build') {
            steps {
                sh '''
                    ./scripts/ci-release-build.sh
                    linux_installer="$WORKSPACE/dist/agent-workflow-$(tr -d '\n' < VERSION)-linux.tar.gz"
                    test -s "$linux_installer" || {
                        echo "Linux installer bundle is missing: $linux_installer" >&2
                        exit 2
                    }
                    echo "Linux installer: $linux_installer"
                '''
            }
        }
        stage('Plugin and contract compatibility') {
            parallel {
                stage('Benchmark plugin') {
                    steps {
                        sh '''
                            compat="$WORKSPACE@tmp/benchmark-compat"
                            wheel="$WORKSPACE/dist/agent_workflow-$(tr -d '\n' < "$WORKSPACE/VERSION")-py3-none-any.whl"
                            rm -rf "$compat"
                            python3 -m venv "$compat/venv"
                            test -s "$wheel"
                            "$compat/venv/bin/pip" install --disable-pip-version-check "$wheel"
                            git clone --depth 1 https://github.com/ngallodev-software/agent-workflow-benchmark.git "$compat/source"
                            git -C "$compat/source" checkout --detach 7619465ba8c0d205d101dd5ea0db8b73c4b2748e
                            "$compat/venv/bin/pip" install --disable-pip-version-check "$compat/source[test]"
                            printf '%s\n' 'schema_version = 1' '' '[plugins]' 'enabled = ["agent-workflow-benchmark"]' > "$compat/config.toml"
                            "$compat/venv/bin/agent-workflow" --config "$compat/config.toml" benchmark --help
                            "$compat/venv/bin/python" -m pytest -q "$compat/source/tests/test_plugin.py"
                        '''
                    }
                }
                stage('Built-in TypeSafe provider') {
                    steps {
                        sh '''
                            compat="$WORKSPACE@tmp/typesafe-compat"
                            wheel="$WORKSPACE/dist/agent_workflow-$(tr -d '\n' < "$WORKSPACE/VERSION")-py3-none-any.whl"
                            rm -rf "$compat"
                            python3 -m venv "$compat/venv"
                            test -s "$wheel"
                            "$compat/venv/bin/pip" install --disable-pip-version-check "$wheel[typesafe]"
                            "$compat/venv/bin/agent-workflow" decision typesafe
                            "$compat/venv/bin/agent-workflow" decision modes
                        '''
                    }
                }
                stage('Shared contract bundle') {
                    steps {
                        sh '''
                            compat="$WORKSPACE@tmp/contracts-compat"
                            wheel="$WORKSPACE/dist/agent_workflow-$(tr -d '\n' < "$WORKSPACE/VERSION")-py3-none-any.whl"
                            rm -rf "$compat"
                            python3 -m venv "$compat/venv"
                            test -s "$wheel"
                            "$compat/venv/bin/pip" install --disable-pip-version-check "$wheel"
                            git clone --depth 1 --branch v0.2.1 https://github.com/ngallodev-software/agent-workflow-spec-contracts.git "$compat/source"
                            "$compat/venv/bin/pip" install --disable-pip-version-check "$compat/source" "pytest>=8,<10"
                            "$compat/venv/bin/python" -m pytest -q "$compat/source/tests"
                            "$compat/venv/bin/python" -c 'from agent_workflow.shared_contracts import negotiate_bundle; from specgen_contracts.bundle import BUNDLE_VERSION, schema_digest; assert negotiate_bundle({"bundle_version":BUNDLE_VERSION,"schema_id":"agent-workflow/prompt-pack/v2","schema_digest":schema_digest("agent-workflow/prompt-pack/v2")})["schema_id"] == "agent-workflow/prompt-pack/v2"'
                        '''
                    }
                }
            }
        }
    }
}
