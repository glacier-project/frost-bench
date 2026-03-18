#!/usr/bin/env bash

METRICS=("DISTANCE" "ID")
OUTPUT_DIR="results/lego-3-recipes/lego-sim-$(date +%Y%m%d_%H%M%S)"
FROST_CONFIG="resource/lego_3_sim.yml"

for METRIC in "${METRICS[@]}"; do
    echo "Running lego recipe simulation with FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC}"

    FROST_CONFIG="${FROST_CONFIG}" METRIC="${METRIC}" OUTPUT_DIR="${OUTPUT_DIR}" RUN_TYPE="sim" ./bin/Lego3Sim
done
