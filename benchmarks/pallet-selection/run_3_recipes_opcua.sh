#!/usr/bin/env bash

METRICS=("DISTANCE" "ID")
OUTPUT_DIR="results/lego/lego-opcua-$(date +%Y%m%d_%H%M%S)"
FROST_CONFIG="resource/lego_3_opcua.yml"

for METRIC in "${METRICS[@]}"; do
    echo "Running lego recipe opcua with FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC}"

    FROST_CONFIG="${FROST_CONFIG}" METRIC="${METRIC}" OUTPUT_DIR="${OUTPUT_DIR}" RUN_TYPE="opcua" ./bin/Lego3Opcua
done
