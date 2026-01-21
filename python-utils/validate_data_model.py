import argparse
from machine_data_model.builder.data_model_builder import DataModelBuilder

def parse_args():
    parser = argparse.ArgumentParser(description="Validate a data model YAML file.")
    parser.add_argument("--data-model", type=str, required=True, help="Path to the data model YAML file to validate.")
    return parser.parse_args()

def main():
    args = parse_args()
    data_model = DataModelBuilder().get_data_model(data_model_path=args.data_model)

if __name__ == "__main__":
    main()