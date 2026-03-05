#!/usr/bin/env bash

METRICS=("ID" "DISTANCE")
INSTANCES=("instance_empty.json") # "instance_mini.json" "instance_small.json" "instance_medium.json" "instance_large.json")
OUTPUT_DIR="lego/opcua-lego-$(date +%Y%m%d_%H%M%S)"
FROST_CONFIG="resource/lego-config.yml"
SAVE_PUPDATES="true"

for METRIC in "${METRICS[@]}"; do
    echo "Running opcua with FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC} and INSTANCE=${INSTANCE}"

    FROST_CONFIG="${FROST_CONFIG}" METRIC="${METRIC}" INSTANCE="${INSTANCE_PATH}" OUTPUT_DIR="${OUTPUT_DIR}" SAVE_PUPDATES="${SAVE_PUPDATES}" ./bin/LegoUA
    sleep 20
  done
done
