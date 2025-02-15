import logging
import sys
from pathlib import Path
from typing import Dict
from .config_manager import ConfigManager
from .file_handler import FileHandler
from .handlers import CommandHandlers

class A3EDA:
    """Main coordinator class for A3EDA operations."""
    
    def __init__(self, args):
        """Initialize A3EDA with command line arguments."""
        self.setup_logging(args.log)
        self.args = args
        self.system_dir = Path.cwd()
        
        # Initialize components
        self.config_manager = ConfigManager(args.yaml_config)
        self.file_handler = FileHandler(self.system_dir)
        
        # Set up data directories structure
        self.data_dirs = self._initialize_data_dirs()
        
        # Initialize command handlers
        self.handlers = CommandHandlers(
            self.config_manager,
            self.system_dir,
            self.data_dirs
        )

    @staticmethod
    def setup_logging(level: str) -> None:
        """Set up logging configuration."""
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            stream=sys.stdout
        )

    def _initialize_data_dirs(self) -> Dict[str, Path]:
        """Initialize data directory structure."""
        return {
            'data': self.system_dir / 'data',
            'raw': self.system_dir / 'data' / 'raw',
            'profiles': self.system_dir / 'data' / 'profiles'
        }

    def run(self) -> None:
        """Execute the requested command."""
        try:
            if self.args.generate:
                self.handlers.handle_generation(self.args.overwrite, self.args.run)
            elif self.args.run:
                self.handlers.handle_running(self.args.run)
            elif self.args.extract:
                self.handlers.handle_extraction()
            else:
                self.handlers.handle_status_check()
        except Exception as e:
            logging.error(f"Error during execution: {e}")
            raise