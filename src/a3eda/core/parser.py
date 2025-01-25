import argparse

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='A3EDA: Automated Analysis of Electronic Structure Data',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('yaml_config', type=str, help='Path to the configuration YAML file')
    parser.add_argument(
        '-l', '--log', type=str, default='info',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        help='Logging level'
    )
    parser.add_argument(
        '-o', '--overwrite', type=str,
        choices=['all', 'nofile', 'CRASH', 'terminated', 'SUCCESSFUL', 'running'],
        help='Overwrite input files based on their status'
    )
    parser.add_argument(
        '-g', '--generate', action='store_true',
        help='Generate input files and optionally execute calculations'
    )
    parser.add_argument(
        '-r', '--run', type=str,
        choices=['all', 'nofile', 'CRASH', 'terminated', 'SUCCESSFUL', 'running'],
        help='Execute input files based on their status'
    )
    parser.add_argument(
        '-e', '--extract', action='store_true',
        help='Extract data from output files and generate energy profiles'
    )
    return parser.parse_args()