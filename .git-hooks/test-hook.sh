#!/usr/bin/env bash
set -uo pipefail

./scripts/compose-wrapper.sh run --build --rm test-runner & test_runner_pid=$!
./scripts/compose-wrapper.sh run --build --rm scripts-tests & scripts_tests_pid=$!
./scripts/compose-wrapper.sh run --build --rm bats-tests & bats_tests_pid=$!
./scripts/compose-wrapper.sh run --build --rm backend-test & backend_test_pid=$!
./scripts/compose-wrapper.sh run --build --rm frontend-test & frontend_test_pid=$!

wait "$test_runner_pid"; test_runner_rc=$?
wait "$scripts_tests_pid"; scripts_tests_rc=$?
wait "$bats_tests_pid"; bats_tests_rc=$?
wait "$backend_test_pid"; backend_test_rc=$?
wait "$frontend_test_pid"; frontend_test_rc=$?

[ "$test_runner_rc" -eq 0 ] && [ "$scripts_tests_rc" -eq 0 ] && [ "$bats_tests_rc" -eq 0 ] && [ "$backend_test_rc" -eq 0 ] && [ "$frontend_test_rc" -eq 0 ]
