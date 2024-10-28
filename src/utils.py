# src/utils.py

import shutil
import zipfile
import logging
from PIL import Image
import os
import re

def create_placeholder_icon(package_path):
    """
    Creates a placeholder icon.png if no default icon is provided.
    """
    icon_path = os.path.join(package_path, 'icon.png')
    try:
        img = Image.new('RGBA', (256, 256), color=(73, 109, 137))
        img.save(icon_path)
        logging.info(f"Created placeholder icon.png at {icon_path}")
    except ImportError:
        logging.warning("Pillow library not installed. Cannot create icon.png.")
    except Exception as e:
        logging.error(f"Failed to create placeholder icon.png at {icon_path}: {e}")

def zip_directory(folder_path, zip_path):
    """
    Zips the contents of a directory.
    """
    try:
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', folder_path)
        logging.info(f"Zipped directory {folder_path} to {zip_path}")
    except Exception as e:
        logging.error(f"Failed to zip directory {folder_path}: {e}")
        raise

def sanitize_readme(description):
    """
    Sanitizes the README description for compatibility with Thunderstore.
    Removes or modifies markdown elements that may not be supported.
    """
    # Remove HTML line breaks
    description = description.replace('<br>', '\n').replace('<BR>', '\n')

    # Remove any HTML tags
    description = re.sub(r'<[^>]+>', '', description)

    # Optionally, limit to certain markdown features or convert certain elements
    # For example, remove code blocks or inline HTML

    return description