#!/usr/bin/env bash

METRICS=("ID")
OUTPUT_DIR="lego/opcua-lego-$(date +%Y%m%d_%H%M%S)"
FROST_CONFIG="resource/lego_conveyor_movements.yml"
SAVE_PUPDATES="true"

for METRIC in "${METRICS[@]}"; do
    echo "Running opcua with FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC}"

    FROST_CONFIG="${FROST_CONFIG}" METRIC="${METRIC}" OUTPUT_DIR="${OUTPUT_DIR}" SAVE_PUPDATES="${SAVE_PUPDATES}" ./bin/LegoUA
done
