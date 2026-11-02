#!/usr/bin/env bash
# Runs a command with the CI credentials removed from its environment: every
# GITHUB_*, ACTIONS_*, RUNNER_*, GH_* and INPUT_* variable (GITHUB_TOKEN,
# ACTIONS_RUNTIME_TOKEN, ACTIONS_ID_TOKEN_REQUEST_*, ...) plus the registry
# tokens (CARGO_REGISTRY_TOKEN, CARGO_REGISTRIES_*), NODE_AUTH_TOKEN and
# NPM_TOKEN. For commands that compile dependencies (`cargo package` verifies
# by building, which runs dependency build.rs scripts and proc-macros) on a
# runner whose job holds credentials the build does not need.
#
# Usage: release-scrub-env.sh <command> [args...]
set -euo pipefail

unset_args=()
while IFS= read -r name; do
    if [[ $name =~ ^(GITHUB_|ACTIONS_|RUNNER_|GH_|INPUT_|CARGO_REGISTRY_|CARGO_REGISTRIES_) ||
        $name == NODE_AUTH_TOKEN || $name == NPM_TOKEN ]]; then
        unset_args+=(-u "$name")
    fi
done < <(compgen -e)

exec env ${unset_args[@]+"${unset_args[@]}"} "$@"
