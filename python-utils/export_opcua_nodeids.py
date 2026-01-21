from asyncua import Client
import pandas as pd
import argparse
import asyncio
from asyncua import ua
from asyncua import Node
from asyncua.ua import ObjectIds, NodeClass
from asyncua.ua.uaprotocol_auto import Argument
import re




def parse_args():
    parser = argparse.ArgumentParser(description="Export OPC UA server model to Excel.")
    parser.add_argument("--url", type=str, help="OPC UA server URL")
    parser.add_argument("--output", type=str, default="opcua_model.xlsx", help="Output Excel file name")
    parser.add_argument("--security_string", type=str, default="None", help="Security string for the OPC UA server")
    parser.add_argument("--username", type=str, default="None", help="Username for the OPC UA server")
    parser.add_argument("--password", type=str, default="None", help="Password for the OPC UA server")
    return parser.parse_args()

async def main(url: str, output: str, security_string: str = "None", username: str = "None", password: str = "None"):
    client = Client(url)
    if security_string != "None":
        await client.set_security_string(security_string+",my_cert.der,my_private_key.pem")
    if username != "None" and password != "None":
        client.set_user(username)
        client.set_password(password)


    await client.connect()

    node: Node = client.nodes.root
    nodes = []

    async def recurse(node: Node, parent: Node | None, path: str = ""):
        children = await node.get_children(ObjectIds.HierarchicalReferences, NodeClass.Method)
        children += await node.get_children(ObjectIds.HierarchicalReferences, NodeClass.Object)
        children += await node.get_children(ObjectIds.HierarchicalReferences, NodeClass.Variable)

        for child in children:
            try:
                name = (await child.read_browse_name()).Name
            except Exception as e:
                print(f"Error reading browse name for node {child}: {e}")
                continue

            # skip names that contain "Types", "ServerDiagnostics", "ServerCapabilities", "Server", "Users", or "Session" in the path
            if name in ["Types", "ServerDiagnostics", "ServerCapabilities", "Server", "Users", "Sessions", "Aliases", "CommDrivers"]:
                continue

            nodeid = str(child.nodeid.to_string())
            parent_nodeid = str(parent.nodeid.to_string()) if parent else "None"

            datatype = ua.VariantType.Null
            try:
                datatype = await child.read_data_type_as_variant_type()
            except Exception as e:
                pass

            nodes.append({"Path": path + "/" + name, "NodeId": nodeid, "ParentID": parent_nodeid, "DataType": datatype.name})

            #if the node is InputArguments or OutputArguments, recurse into it
            if name in ["InputArguments", "OutputArguments"]:
                try:
                    args = await child.get_value()
                except Exception as e:
                    print(f"Error reading arguments for node {child}: {e}")
                    continue
                for arg in args:
                    arg_name = arg.Name
                    arg_type = arg.DataType.to_string() if arg.DataType else "Null"
                    path += "/" + name
                    if arg_name is None:
                        arg_name = "UnnamedArgument"
                    path += "/" + arg_name
                    nodes.append({
                        "Path": path,
                        "NodeId": "None",
                        "ParentID": nodeid,
                        "DataType": arg_type
                    })

            await recurse(child, node, path + "/" + name)

    await recurse(node, parent=None)

    df = pd.DataFrame(nodes)
    df.to_csv(output, index=False)

    await client.disconnect()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args.url, args.output, args.security_string, args.username, args.password))