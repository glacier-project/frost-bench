# Frost Template

A template repository for quickly starting new [Frost](https://github.com/esd-univr/frost) projects.

## Overview

This template provides a minimal, ready-to-use starting point for developing Cyber-Physical Production System (CPPS) virtual platforms using the Frost framework. It includes the essential directory structure, configuration files, and a basic main reactor setup that you can extend for your specific use case.

## About Frost

Frost is an open-source framework for the development, testing, and deployment of software applications for controlling and supervising CPPSs. Built on top of the [Lingua Franca](https://www.lf-lang.org/) framework, Frost ensures deterministic execution and provides:

- **Simplified interface** for machine control software development
- **Digital Twin capabilities** for virtual testing before deployment
- **Extensible components** (FrostMachine, FrostBus, FrostReactor, etc.)
- **Data model-driven architecture** for defining flexible machine interfaces

Frost is part of the [Glacier](https://github.com/esd-univr/glacier) project.

## Prerequisites

- [Lingua Franca](https://www.lf-lang.org/) compiler (`lfc`)
- Python 3.11 or higher
- [Frost framework](https://github.com/esd-univr/frost) (included as a submodule in this template)

## Getting Started

### 1. Clone this template

```bash
git clone https://github.com/esd-univr/frost-template.git your-project-name
cd your-project-name
```

### 2. Initialize the Frost submodule

```bash
git submodule update --init --recursive
```

### 3. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 4. Configure your project

Edit the configuration file at `resources/frost_config.yml` to customize:
- Logging time precision
- Logging level of each reactor
- Reactor initial parameters
- Data model paths

See the [Configuration](#configuration) section below for detailed information.

### 5. Customize your data model

Edit or replace `resources/data_model/hello.yml` to define your machine's data model, including:
- Variables (numerical, string, boolean, object)
- Methods
- Folder structure

### 6. Implement your application

Edit `src/Main.lf` to:
- Import custom machine reactors
- Instantiate your machines
- Configure the FrostBus connections

### 7. Build and run

```bash
lfc src/Main.lf
./bin/Main
```

## Project Structure

```
frost-template/
├── src/
│   └── Main.lf              # Main reactor file - entry point
├── resources/
│   ├── frost_config.yml     # Frost configuration
│   └── data_model/
│       └── frost_bus.yml    # Bus data model 
│       └── hello.yml        # Hello data model
├── frost/                   # Frost framework (submodule)
│   ├── src/
│   │   ├── lib/             # Frost library components
│   │   └── python_lib/      # Python utilities
│   └── benchmark/           # Example implementations
└── README.md
```

## Example: Creating a Simple Machine

Create a new file `src/MyMachine.lf`:

```lf
target Python

import FrostMachine from "../frost/src/lib/FrostMachine.lf"

reactor MyMachine extends FrostMachine {
    state my_variable
    
    reaction(startup) {=
        # Link state variables to data model nodes
        self.my_variable = self.data_model.get_node("MyMachine/Status")
        self.logger.info("MyMachine initialized")
    =}
    
    timer t(0 s, 1 s)
    reaction(t) {=
        # Implement your machine logic here
        self.my_variable.value += 1
        self.logger.info("Status updated: %d", self.my_variable.value)
    =}
}
```

Then update `src/Main.lf` to instantiate it:

```lf
import MyMachine from "MyMachine.lf"

main reactor {
    bus = new FrostBus(name="frost_bus", width=1)
    machine = new MyMachine(
        name="my_machine",
        model_path="path/to/my_machine_model.yml"
    )
    
    bus.channel_out -> machine.channel_in
    machine.channel_out -> bus.channel_in after 0
}
```

## Configuration

Frost uses a YAML configuration file (`resources/frost_config.yml`) to manage reactor parameters and logging settings. The configuration follows a hierarchical structure that mirrors the reactor instantiation.

### Global Settings

```yaml
time_precision: MSECS    # Time precision: NSECS, USECS, MSECS, SECS
logging_level: INFO      # Global logging level: DEBUG, INFO, WARNING, ERROR
```

### Reactor Configuration

Each reactor is configured under the `reactors` key using its **name** (the `name` parameter passed during instantiation):

```yaml
reactors:
  hello:                              # Matches: new Hello(name="hello")
    logging_level: INFO               # Override global logging level
    parameters:
      data_model_path: "resources/data_model/hello.yml"  # Path to data model
    reactors:                         # Nested reactors (if any)
      some_reactor:                  # Matches: new SomeReactor(name="hello.some_reactor")
        logging_level: INFO
```

### Key Concepts

1. **Name Matching**: The configuration keys must match the `name` parameter you provide when instantiating reactors in your `.lf` files.

2. **Hierarchical Structure**: Nested reactors are configured under their parent's `reactors` section.

3. **Parameter Passing**: The `parameters` section allows you to set initial values for reactor parameters, particularly:
   - `data_model_path`: Path to the YAML data model file
   - Any state variables defined in the reactor

4. **Logging Levels**: Each reactor can have its own logging level, overriding the global setting. This is useful for debugging specific components without flooding logs.

## Docker Support

The template includes Docker support for containerized development and deployment.

### Building the Docker Image

```bash
docker build -t frost-app .
```

The Dockerfile performs the following steps:
1. Installs Lingua Franca compiler (`lfc`)
2. Installs Python dependencies from `requirements.txt`
3. Compiles the `src/Main.lf` file
4. Creates a minimal runtime image with only the necessary components

### Running the Container

```bash
docker run --rm frost-app
```

## Documentation

For more detailed information about Frost and its components, please refer to the following resources:
- [Lingua Franca Documentation](https://www.lf-lang.org/docs)
- [Frost Repository](https://github.com/esd-univr/frost)
- [Machine Data Model](https://github.com/esd-univr/machine-data-model)
- [Glacier Project](https://github.com/esd-univr/glacier)

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

See [LICENSE](LICENSE) file for details.

## Support

For questions and support, please open an issue in the repository.