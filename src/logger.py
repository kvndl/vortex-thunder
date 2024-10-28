# src/logger.py

import logging
import sys

def setup_logging():
    """
    Configures logging to output to both console and a log file.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler
    fh = logging.FileHandler('vthunder.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
