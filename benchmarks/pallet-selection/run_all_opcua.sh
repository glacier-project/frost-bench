#!/usr/bin/env bash

METRICS=("DISTANCE" "RANDOM" "ID" )
INSTANCES=("instance_empty.json") # "instance_mini.json" "instance_small.json" "instance_medium.json" "instance_large.json")
OUTPUT_DIR="results/$(date +%Y%m%d_%H%M%S)"
FROST_CONFIG="resource/frost_config_opcua.yml"
SAVE_PUPDATES="true"

for METRIC in "${METRICS[@]}"; do
  for INSTANCE in "${INSTANCES[@]}"; do
    echo "Running simulation with FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC} and INSTANCE=${INSTANCE}"
    INSTANCE_PATH="resource/instance/${INSTANCE}"
    
    FROST_CONFIG="${FROST_CONFIG}" METRIC="${METRIC}" INSTANCE="${INSTANCE_PATH}" OUTPUT_DIR="${OUTPUT_DIR}" SAVE_PUPDATES="${SAVE_PUPDATES}" ./bin/Conveyor
  done
done