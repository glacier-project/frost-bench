#!/usr/bin/env bash

METRICS=("DISTANCE" "ID")
OUTPUT_DIR="results/lego/movements-opcua-$(date +%Y%m%d_%H%M%S)"
FROST_CONFIG="resource/lego_movements_opcua.yml"

for METRIC in "${METRICS[@]}"; do
    echo "Running lego movements opcua with FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC}"

    FROST_CONFIG="${FROST_CONFIG}" METRIC="${METRIC}" OUTPUT_DIR="${OUTPUT_DIR}" RUN_TYPE="opcua" ./bin/LegoMovementsOpcua
done
