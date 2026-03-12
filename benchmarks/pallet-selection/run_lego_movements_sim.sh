#!/usr/bin/env bash

METRICS=("DISTANCE" "ID")
OUTPUT_DIR="results/lego/movements-sim-$(date +%Y%m%d_%H%M%S)"
FROST_CONFIG="resource/lego_movements_sim.yml"

for METRIC in "${METRICS[@]}"; do
    echo "Running lego movements simulation with FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC}"

    FROST_CONFIG="${FROST_CONFIG}" METRIC="${METRIC}" OUTPUT_DIR="${OUTPUT_DIR}" RUN_TYPE="sim" ./bin/LegoMovementsSim
done
