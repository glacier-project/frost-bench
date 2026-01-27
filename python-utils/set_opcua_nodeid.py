import argparse

import pandas as pd
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.builder.data_model_dumper import DataModelDumper
from machine_data_model.nodes.connectors.opcua_connector import OpcuaRemoteResourceSpec
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import ObjectVariableNode, VariableNode


def parse_args():
    parser = argparse.ArgumentParser(
        description="Set OPC UA NodeIds in the specified data model file."
    )
    parser.add_argument(
        "--data-model",
        type=str,
        required=True,
        help="Path to the data model YAML file to be modified.",
    )
    parser.add_argument(
        "--output", type=str, required=True, help="Path to save the modified data model YAML file."
    )
    parser.add_argument(
        "--opcua-node-ids",
        type=str,
        required=True,
        help="Path of the CSV file containing OPC UA NodeIds in the format 'pallet_id,node_id,parent_id,DataType'.",
    )
    parser.add_argument(
        "--data-model-node",
        type=str,
        default="/",
        help="Path to the data model node from which to start modifications.",
    )
    parser.add_argument(
        "--connector_name",
        type=str,
        default="OpcuaConnector1",
        help="Name of the OPC UA connector to set in the data model nodes.",
    )
    return parser.parse_args()


def _set_opcua_nodeid(node, opcua_node_dict, connector_name):
    node_path = node.qualified_name
    if not isinstance(node, VariableNode):
        print(f"Skipping node {node_path} as it is not a VariableNode.")
        return

    # Set the node ID if the node path exists in the dictionary
    node.set_connector_name(connector_name)
    node.remote_resource_spec = OpcuaRemoteResourceSpec(node_id=opcua_node_dict[node_path])


def main():
    args = parse_args()

    opcua_node_ids = pd.read_csv(
        args.opcua_node_ids, header=None, names=["node_path", "node_id", "parent_id", "DataType"]
    )
    opcua_node_dict = {}
    for _, row in opcua_node_ids.iterrows():
        opcua_node_dict[row["node_path"]] = row["node_id"]

    data_model = DataModelBuilder().get_data_model(data_model_path=args.data_model)
    data_model_node = data_model.get_node(args.data_model_node)

    assert isinstance(
        data_model_node, FolderNode | ObjectVariableNode
    ), f"Data model node at path {args.data_model_node} must be a FolderNode or ObjectVariableNode."
    data_model.traverse(
        data_model_node, lambda node: _set_opcua_nodeid(node, opcua_node_dict, args.connector_name)
    )

    # Save the modified data model
    dumper = DataModelDumper(data_model)
    dumper.dumps(file_path=args.output)


if __name__ == "__main__":
    main()
