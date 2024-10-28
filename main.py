# main.py

import os
import sys
import requests
import logging
import json
import shutil
import zipfile
from datetime import datetime
import time
import re
from PIL import Image

# Ensure your environment variables are set
# NEXUS_API_KEY and THUNDERSTORE_API_KEY

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('vortex-thunder.log')
    ]
)

def load_config(filename='mods.json'):
    """
    Loads the configuration from a JSON file.
    """
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        logging.info(f"Loaded configuration from {filename}.")
        return data
    except FileNotFoundError:
        logging.error(f"Configuration file {filename} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {filename}: {e}")
        sys.exit(1)

def save_config(data, filename='mods.json'):
    """
    Saves the configuration to a JSON file.
    """
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        logging.info(f"Saved configuration to {filename}.")
    except Exception as e:
        logging.error(f"Failed to save configuration to {filename}: {e}")

def create_placeholder_icon(package_path):
    """
    Creates a placeholder icon.png if no default icon is provided.
    """
    icon_path = os.path.join(package_path, 'icon.png')
    try:
        img = Image.new('RGBA', (256, 256), color=(73, 109, 137))
        img.save(icon_path)
        logging.info(f"Created placeholder icon.png at {icon_path}")
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
    # Remove HTML line breaks and tags
    description = re.sub(r'<br\s*/?>', '\n', description, flags=re.IGNORECASE)
    description = re.sub(r'<[^>]+>', '', description)
    return description.strip()

def create_manifest(package_path, mod_name, version, description, dependencies, website_url):
    """
    Creates a manifest.json file for the mod package.
    """
    manifest = {
        "name": mod_name,
        "version_number": version,
        "website_url": website_url,
        "description": description,
        "dependencies": dependencies
    }
    manifest_path = os.path.join(package_path, 'manifest.json')
    try:
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=4)
        logging.info(f"Created manifest.json at {manifest_path}")
    except Exception as e:
        logging.error(f"Failed to create manifest.json at {manifest_path}: {e}")

def create_readme(package_path, mod_info):
    """
    Creates a README.md file for the mod package.
    """
    raw_description = mod_info.get('description', '')
    sanitized_description = sanitize_readme(raw_description)
    readme_content = f"# {mod_info.get('name', 'Unknown Mod')}\n\n{sanitized_description}\n"
    readme_path = os.path.join(package_path, 'README.md')
    try:
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        logging.info(f"Created README.md at {readme_path}")
    except Exception as e:
        logging.error(f"Failed to create README.md at {readme_path}: {e}")

def create_changelog(package_path, mod_info):
    """
    Creates a CHANGELOG.md file for the mod package.
    """
    changelog_content = f"## Version {mod_info.get('version', 'unknown')} - {datetime.now().date()}\n\n- Automated update.\n"
    changelog_path = os.path.join(package_path, 'CHANGELOG.md')
    try:
        with open(changelog_path, 'w') as f:
            f.write(changelog_content)
        logging.info(f"Created CHANGELOG.md at {changelog_path}")
    except Exception as e:
        logging.error(f"Failed to create CHANGELOG.md at {changelog_path}: {e}")

def prepare_package(mod_info, file_path, mod_entry, nexus_game_domain, all_mods):
    """
    Prepares the mod package for Thunderstore.
    """
    mod_name = mod_info.get('name', 'unknown_mod').replace(' ', '_')
    version = mod_info.get('version', 'unknown_version')
    description = mod_info.get('summary', 'No description provided.')
    website_url = f"https://www.nexusmods.com/{nexus_game_domain}/mods/{mod_info.get('mod_id')}"
    package_name = f"{mod_name}_{version}"
    package_path = os.path.join('packages', package_name)
    os.makedirs(package_path, exist_ok=True)

    # Extract the downloaded mod file into the package directory
    try:
        shutil.unpack_archive(file_path, package_path)
        logging.info(f"Extracted {file_path} to {package_path}")
    except Exception as e:
        logging.error(f"Failed to unpack archive {file_path}: {e}")
        return None

    # Retrieve dependencies from mod_entry and format them
    raw_dependencies = mod_entry.get('dependencies', [])
    formatted_dependencies = []
    for dep_name in raw_dependencies:
        dep_entry = next((mod for mod in all_mods if mod['name'] == dep_name), None)
        if dep_entry and dep_entry.get('last_processed_version'):
            dep_author = dep_entry.get('author', 'UnknownAuthor')
            dep_version = dep_entry.get('last_processed_version')
            formatted_dependency = f"{dep_author}-{dep_name}-{dep_version}"
            formatted_dependencies.append(formatted_dependency)
        else:
            logging.warning(f"Dependency '{dep_name}' for mod '{mod_info.get('name')}' not found or not processed yet.")

    # Create required files
    create_manifest(package_path, mod_name, version, description, formatted_dependencies, website_url)
    create_readme(package_path, mod_info)
    create_changelog(package_path, mod_info)
    create_placeholder_icon(package_path)

    # Zip the package
    package_zip = f"{package_path}.zip"
    try:
        zip_directory(package_path, package_zip)
        logging.info(f"Created zip package at {package_zip}")
        return package_zip
    except Exception as e:
        logging.error(f"Failed to zip the package {package_path}: {e}")
        return None

def download_mods(config, session, nexus_game_domain, game_id):
    """
    Handles downloading mods from Nexus Mods.
    """
    mods = config.get('mods', [])
    if not mods:
        logging.error("No mods found in configuration.")
        return

    for mod_entry in mods:
        mod_id = mod_entry['mod_id']
        mod_name = mod_entry.get('name', 'unknown_mod').replace(' ', '_')
        logging.info(f"Processing mod ID: {mod_id}")

        # Get mod info
        mod_info = get_mod_info(session, nexus_game_domain, mod_id)
        if not mod_info:
            logging.error(f"Failed to get mod info for mod ID {mod_id}")
            continue

        current_version = mod_info.get('version')
        last_version = mod_entry.get('last_processed_version')
        if current_version == last_version:
            logging.info(f"No new version for mod ID {mod_id}. Skipping.")
            continue

        # Get latest file info
        latest_file = get_latest_file_info(session, nexus_game_domain, mod_id)
        if not latest_file:
            logging.warning(f"No files found for mod ID {mod_id}. Skipping.")
            continue

        file_id = latest_file['file_id']
        file_name = latest_file['file_name']

        mod_download_dir = os.path.join('downloads', str(mod_id))
        os.makedirs(mod_download_dir, exist_ok=True)

        logging.info(f"Downloading mod '{mod_info.get('name', 'Unknown')}' version {mod_info.get('version', 'unknown')}")
        file_path = download_mod_file(session, nexus_game_domain, mod_id, file_id, file_name, mod_download_dir, game_id)
        if not file_path:
            logging.error(f"Failed to download mod ID {mod_id}")
            continue

        # Prepare package
        package_zip = prepare_package(mod_info, file_path, mod_entry, nexus_game_domain, mods)
        if not package_zip:
            logging.error(f"Failed to prepare package for mod ID {mod_id}")
            continue

        # Update last_processed_version and save config
        mod_entry['last_processed_version'] = current_version
        save_config(config)

def get_mod_info(session, nexus_game_domain, mod_id):
    """
    Retrieves mod information from Nexus Mods API.
    """
    url = f'https://api.nexusmods.com/v1/games/{nexus_game_domain}/mods/{mod_id}.json'
    try:
        response = session.get(url)
        if response.status_code == 403:
            logging.error(f"403 Forbidden when accessing mod ID {mod_id}. Check your API key and session cookies.")
            return None
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching mod info for mod ID {mod_id}: {e}")
        return None

def get_latest_file_info(session, nexus_game_domain, mod_id):
    """
    Retrieves the latest file information for a mod.
    """
    url = f'https://api.nexusmods.com/v1/games/{nexus_game_domain}/mods/{mod_id}/files.json'
    try:
        response = session.get(url)
        if response.status_code == 403:
            logging.error(f"403 Forbidden when accessing files for mod ID {mod_id}.")
            return None
        response.raise_for_status()
        files = response.json().get('files', [])
        if not files:
            logging.warning(f"No files found for mod ID {mod_id}.")
            return None
        latest_file = max(files, key=lambda x: x.get('uploaded_timestamp', 0))
        return latest_file
    except Exception as e:
        logging.error(f"Error fetching files for mod ID {mod_id}: {e}")
        return None

def download_mod_file(session, nexus_game_domain, mod_id, file_id, file_name, mod_download_dir, game_id):
    """
    Downloads the mod file from Nexus Mods.
    """
    url = 'https://www.nexusmods.com/Core/Libs/Common/Managers/Downloads?GenerateDownloadUrl'
    referer_url = f'https://www.nexusmods.com/{nexus_game_domain}/mods/{mod_id}?tab=files&file_id={file_id}'
    headers = {
        'Referer': referer_url,
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://www.nexusmods.com',
        'X-Requested-With': 'XMLHttpRequest'
    }
    data = {
        'fid': file_id,
        'game_id': game_id
    }
    try:
        response = session.post(url, headers=headers, data=data)
        if response.status_code == 403:
            logging.error(f"403 Forbidden when generating download URL for mod ID {mod_id} file ID {file_id}.")
            return None
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Error getting download link for mod ID {mod_id}: {e}")
        return None

    try:
        download_info = response.json()
        download_url = download_info.get('url')
        if not download_url:
            logging.error(f"No download URL found for mod ID {mod_id}.")
            return None
    except Exception as e:
        logging.error(f"Error parsing download info for mod ID {mod_id}: {e}")
        return None

    try:
        logging.info(f"Downloading from {download_url}")
        download_response = session.get(download_url, stream=True)
        if download_response.status_code == 403:
            logging.error(f"403 Forbidden when downloading mod ID {mod_id}.")
            return None
        download_response.raise_for_status()
        file_path = os.path.join(mod_download_dir, file_name)
        with open(file_path, 'wb') as f:
            for chunk in download_response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"Successfully downloaded {file_name} for mod ID {mod_id}")
        return file_path
    except Exception as e:
        logging.error(f"Error downloading mod ID {mod_id}: {e}")
        return None

def upload_mods(config):
    """
    Handles uploading mods to Thunderstore.
    """
    thunderstore_api_key = os.getenv('THUNDERSTORE_API_KEY')
    if not thunderstore_api_key:
        logging.error("THUNDERSTORE_API_KEY not set. Please set it as an environment variable.")
        sys.exit(1)

    team_name = config.get('team_name', 'community')
    headers = {
        'Authorization': f'Bearer {thunderstore_api_key}'
    }

    mods = config.get('mods', [])
    if not mods:
        logging.error("No mods found in configuration.")
        return

    for mod_entry in mods:
        mod_id = mod_entry['mod_id']
        mod_name = mod_entry.get('name', 'unknown_mod').replace(' ', '_')
        version = mod_entry.get('last_processed_version')
        if not version:
            logging.info(f"No processed version for mod ID {mod_id}. Skipping upload.")
            continue

        package_zip = os.path.join('packages', f"{mod_name}_{version}.zip")
        if not os.path.exists(package_zip):
            logging.error(f"Package {package_zip} does not exist. Skipping upload.")
            continue

        categories = mod_entry.get('categories', ['Misc'])

        logging.info(f"Uploading package {package_zip} to Thunderstore.")
        upload_url = 'https://thunderstore.io/api/v1/package/upload/'
        try:
            with open(package_zip, 'rb') as f:
                files = {'file': f}
                data = {
                    'team': team_name,
                    'categories': ','.join(categories)
                }
                response = requests.post(upload_url, headers=headers, files=files, data=data)
                if response.status_code == 403:
                    logging.error(f"403 Forbidden when uploading {package_zip} to Thunderstore.")
                    continue
                response.raise_for_status()
                logging.info(f"Uploaded {package_zip} to Thunderstore successfully.")
        except Exception as e:
            logging.error(f"Error uploading {package_zip}: {e}")

def main():
    """
    Main function to coordinate downloading and uploading mods.
    """
    # Load configuration
    config = load_config()
    nexus_game_domain = config.get('nexus_game_domain')
    thunderstore_game_domain = config.get('thunderstore_game_domain')
    game_id = config.get('game_id')
    mods = config.get('mods', [])

    if not all([nexus_game_domain, thunderstore_game_domain, game_id]):
        logging.error("nexus_game_domain, thunderstore_game_domain, and game_id must be set in mods.json.")
        sys.exit(1)

    # Initialize a requests.Session
    session = requests.Session()
    session.headers.update({
        'apikey': os.getenv('NEXUS_API_KEY'),
        'Accept': 'application/json',
        'User-Agent': 'vortex-thunder/1.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://www.nexusmods.com'
    })

    # Check for Nexus API key
    nexus_api_key = os.getenv('NEXUS_API_KEY')
    if not nexus_api_key:
        logging.error("NEXUS_API_KEY not set. Please set it as an environment variable.")
        sys.exit(1)

    # Fetch and set session cookies
    try:
        import browser_cookie3
        cj = browser_cookie3.load(domain_name='nexusmods.com')
        session.cookies.update(cj)
        logging.info("Session cookies have been set.")
    except Exception as e:
        logging.warning(f"Failed to fetch browser cookies: {e}")

    # Prompt user to select action
    print("\nSelect an action:")
    print("1. Download mods from Nexus Mods")
    print("2. Upload mods to Thunderstore")
    print("3. Download and upload mods")
    print("4. Exit")
    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        download_mods(config, session, nexus_game_domain, game_id)
    elif choice == '2':
        upload_mods(config)
    elif choice == '3':
        download_mods(config, session, nexus_game_domain, game_id)
        upload_mods(config)
    elif choice == '4':
        sys.exit(0)
    else:
        print("Invalid choice.")
        sys.exit(1)

if __name__ == '__main__':
    main()
