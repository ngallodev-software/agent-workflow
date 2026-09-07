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
        stage('Fetch latest codebase-memory-cli artifact') {
            when {
                expression { return env.CBM_CLI_JENKINS_JOB?.trim() }
            }
            steps {
                withCredentials([usernameColonPassword(credentialsId: 'agent-workflow-local-jenkins-api', variable: 'CBM_CLI_JENKINS_AUTH')]) {
                    sh '''
                    set -eu
                    artifact_dir='jenkins-artifacts/codebase-memory-cli-linux-amd64'
                    base_url="${CBM_CLI_JENKINS_URL:-${JENKINS_URL:?set CBM_CLI_JENKINS_URL or JENKINS_URL}}"
                    job_path="$(printf '%s' "$CBM_CLI_JENKINS_JOB" | sed 's#/#/job/#g')"
                    artifact_url="${base_url%/}/job/${job_path}/lastSuccessfulBuild/artifact/${artifact_dir}"
                    fetch() {
                        if [ -n "${CBM_CLI_JENKINS_AUTH:-}" ]; then
                            curl -fsSLo "$1" -u "$CBM_CLI_JENKINS_AUTH" "$2"
                        else
                            curl -fsSLo "$1" "$2"
                        fi
                    }
                    mkdir -p "$artifact_dir"
                    fetch "$artifact_dir/build.json" "${base_url%/}/job/${job_path}/lastSuccessfulBuild/api/json"
                    for name in SHA256SUMS codebase-memory-cli source-revision version.txt; do
                        fetch "$artifact_dir/$name" "$artifact_url/$name"
                    done
                    sha256sum -c "$artifact_dir/SHA256SUMS"
                    test -x "$artifact_dir/codebase-memory-cli"
                    "$artifact_dir/codebase-memory-cli" --version
                    test -s "$artifact_dir/source-revision"
                    python - "$artifact_dir/build.json" <<'PY'
                    import json
                    import sys
                    build = json.load(open(sys.argv[1], encoding="utf-8"))
                    print(f"codebase-memory-cli upstream build: {build['number']} {build['url']}")
                    PY
                    '''
                }
            }
        }
        stage('Capture synthetic CLI benchmark') {
            when {
                expression { return env.CBM_CLI_JENKINS_JOB?.trim() }
            }
            steps {
                sh '''
                    set -eu
                    artifact_dir='jenkins-artifacts/codebase-memory-cli-linux-amd64'
                    benchmark_dir='jenkins-artifacts/agent-workflow-benchmarks'
                    export PATH="$WORKSPACE/$artifact_dir:$PATH"
                    codebase-memory-cli --version
                    rm -rf "$benchmark_dir"
                    mkdir -p "$benchmark_dir"
                    python --json benchmark suite-export --benchmark-id priority-picker-fast-v1 "$benchmark_dir/suite" > "$benchmark_dir/suite-export.json"
                    python --json benchmark fixture-create "$benchmark_dir/suite/benchmark-spec.json" "$benchmark_dir/fixture" > "$benchmark_dir/fixture-create.json"
                    run_id="jenkins-$BUILD_NUMBER"
                    python --json benchmark plan "$benchmark_dir/suite/benchmark-spec.json" \
                        --executor "$benchmark_dir/suite/executors/synthetic.json" \
                        --repo "$benchmark_dir/fixture" --run-id "$run_id" --repetitions 1 \
                        --worktree-root "$WORKSPACE/.jenkins-benchmark-worktrees" \
                        --codebase-memory-mode cli > "$benchmark_dir/plan.json"
                    plan="$(python -c 'import json; print(json.load(open("jenkins-artifacts/agent-workflow-benchmarks/plan.json"))["run_plan"])')"
                    python --json benchmark run "$plan" > "$benchmark_dir/run.json"
                    python --json benchmark live-stop "$plan" > "$benchmark_dir/live-stop.json"
                    run_dir="$(dirname "$plan")"
                    cp -a "$run_dir" "$benchmark_dir/run"
                    cp "$artifact_dir/source-revision" "$artifact_dir/version.txt" "$benchmark_dir/"
                    test -s "$benchmark_dir/run/report.json"
                    test -s "$benchmark_dir/run/consolidation-receipt.json"
                '''
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
        stage('Install built wheel') {
            steps {
                sh '''
                    set -eu
                    install_python="$VENV/bin/python"
                    test -x "$install_python" || {
                        echo "Jenkins install interpreter is missing: $install_python" >&2
                        exit 2
                    }
                    wheel="$(find "$WORKSPACE/dist" -maxdepth 1 -type f -name 'agent_workflow-*.whl' -print -quit)"
                    test -n "$wheel" || {
                        echo 'built agent-workflow wheel is missing' >&2
                        exit 2
                    }
                    test -x "$WORKSPACE/install.sh" || {
                        echo "workspace install root is invalid: $WORKSPACE" >&2
                        exit 2
                    }
                    AGENT_WORKFLOW_INSTALL_PYTHON="$install_python" \
                        "$WORKSPACE/install.sh" --wheel "$wheel" --extras mcp \
                        --no-mcp-register --no-hooks --no-skills
                    expected_version="$(tr -d '\n' < VERSION)"
                    installed_version="$("$install_python" -c \
                        'from importlib.metadata import version; print(version("agent-workflow"))')"
                    test "$installed_version" = "$expected_version" || {
                        echo "installed agent-workflow version $installed_version != $expected_version" >&2
                        exit 2
                    }
                    echo "Installed agent-workflow version: $installed_version"
                '''
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'jenkins-artifacts/**', fingerprint: true, allowEmptyArchive: true
        }
    }
}
