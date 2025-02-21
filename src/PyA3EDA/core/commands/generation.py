"""
Generation Command Module

Handles the "generate" command from the CLI.
Creates an instance of the WorkflowManager and calls its generate_inputs() method.
"""

import logging
from PyA3EDA.core.config.config_manager import ConfigManager
from PyA3EDA.core.workflow.workflow_manager import WorkflowManager
from PyA3EDA.core.utils.argument_parser import parse_arguments

def run_generation(config_path: str) -> None:
    config_manager = ConfigManager(config_path)
    workflow = WorkflowManager(config_manager)
    workflow.generate_inputs()

if __name__ == "__main__":
    args = parse_arguments()
    run_generation(args.yaml_config)
