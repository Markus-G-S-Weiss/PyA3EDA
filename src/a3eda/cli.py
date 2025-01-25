from .core.parser import parse_arguments
from .core.a3eda import A3EDA
import logging
import sys

def main():
    args = parse_arguments()
    try:
        a3eda = A3EDA(args)
        a3eda.run()
    except Exception as e:
        logging.error(f"Error during execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()