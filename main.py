#!/usr/bin/env python3

import os
import requests
import json
import zipfile
import shutil
import logging
from datetime import datetime
import time  # For retry delays
import browser_cookie3  # For fetching browser cookies

# Configure logging to output to console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("vt.log")
    ]
)

def get_nexusmods_session_cookie():
    """
    Fetches the 'nexusmods_session' cookie from Firefox or Chromium browsers.
    Returns the cookie value if found, else None.
    """
    # Try fetching from Firefox
    try:
        cj = browser_cookie3.firefox(domain_name='nexusmods.com')
        for cookie in cj:
            if cookie.name == 'nexusmods_session':
                logging.info("nexusmods_session cookie found in Firefox.")
                return cookie.value
    except Exception as e:
        logging.warning(f"Firefox cookies not accessible: {e}")
    
    # Try fetching from Chromium-based browsers
    try:
        cj = browser_cookie3.chrome(domain_name='nexusmods.com')
        for cookie in cj:
            if cookie.name == 'nexusmods_session':
                logging.info("nexusmods_session cookie found in Chromium.")
                return cookie.value
    except Exception as e:
        logging.warning(f"Chromium cookies not accessible: {e}")
    
    logging.error("nexusmods_session cookie not found in Firefox or Chromium browsers.")
    return None

# Load API keys from environment variables
NEXUS_API_KEY = os.getenv('NEXUS_API_KEY')
THUNDERSTORE_API_KEY = os.getenv('THUNDERSTORE_API_KEY')

# Fetch the nexusmods_session cookie using browser_cookie3
NEXUS_SESSION_COOKIE = get_nexusmods_session_cookie()

# Check if API keys and session cookie are set
if not NEXUS_API_KEY or not NEXUS_SESSION_COOKIE or not THUNDERSTORE_API_KEY:
    logging.error("API keys and/or nexusmods_session cookie not set.")
    exit(1)

# Initialize a session to persist headers and cookies
session = requests.Session()

# Update headers to include 'proxy-token' with the value of 'nexusmods_session'
session.headers.update({
    'apikey': NEXUS_API_KEY,
    'Accept': 'application/json',
    'User-Agent': 'vortex-thunder/1.0 (admin@kvndl.xyz)',
    'proxy-token': NEXUS_SESSION_COOKIE  # Ensure this is the correct value to use
})

# Define a list of cookies
cookies = [
    {'name': 'nexusmods_session', 'value': NEXUS_SESSION_COOKIE},
    # Add other cookies here if needed
    # Example:
    # {'name': 'another_cookie', 'value': 'cookie_value'},
]

# Add cookies to the session
for cookie in cookies:
    session.cookies.set(cookie['name'], cookie['value'])

# Thunderstore headers remain the same
THUNDERSTORE_HEADERS = {
    'Authorization': f'Bearer {THUNDERSTORE_API_KEY}'
}

def load_mod_list(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def save_mod_list(mod_list, filename):
    with open(filename, 'w') as f:
        json.dump(mod_list, f, indent=4)

def get_mod_info(mod_id, nexus_game_domain):
    url = f'https://api.nexusmods.com/v1/games/{nexus_game_domain}/mods/{mod_id}.json'
    try:
        response = session.get(url)
        response.raise_for_status()
        logging.info(f"Retrieved info for mod ID {mod_id}.")
        return response.json()
    except requests.HTTPError as e:
        logging.error(f"Failed to get mod info for mod ID {mod_id}: {e}")
        raise

def get_latest_file_info(mod_id, nexus_game_domain):
    url = f'https://api.nexusmods.com/v1/games/{nexus_game_domain}/mods/{mod_id}/files.json'
    for attempt in range(5):  # Retry up to 5 times if rate limited
        try:
            response = session.get(url)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', '60'))
                logging.warning(f"Rate limited when fetching files for mod ID {mod_id}. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            files = response.json().get('files', [])
            if not files:
                logging.warning(f"No files found for mod ID {mod_id}.")
                return None
            # Select the most recently uploaded file
            latest_file = max(files, key=lambda x: x.get('uploaded_timestamp', ''))
            logging.info(f"Latest file for mod ID {mod_id}: {latest_file.get('file_name')}")
            return latest_file
        except requests.HTTPError as e:
            logging.error(f"Error fetching files for mod ID {mod_id}: {e}")
            raise
    logging.error(f"Failed to retrieve file info for mod ID {mod_id} after multiple attempts.")
    return None

def is_new_version(mod_info, mod_entry):
    current_version = mod_info.get('version')
    last_version = mod_entry.get('last_processed_version')
    is_new = current_version != last_version
    if is_new:
        logging.info(f"New version detected for mod ID {mod_entry['mod_id']}: {current_version}")
    else:
        logging.info(f"No new version for mod ID {mod_entry['mod_id']}.")
    return is_new

def download_mod_file(mod_id, file_id, file_name, mod_download_dir, nexus_game_domain):
    url = f'https://api.nexusmods.com/v1/games/{nexus_game_domain}/mods/{mod_id}/files/{file_id}/download_link.json'
    try:
        response = session.get(url)
        response.raise_for_status()
        logging.info(f"Retrieved download links for mod ID {mod_id}, file ID {file_id}.")
    except requests.HTTPError as e:
        logging.error(f"Failed to get download link for mod ID {mod_id}, file ID {file_id}: {e}")
        return None

    download_links = response.json()
    if not download_links:
        logging.error(f"No download URLs found for mod ID {mod_id}, file ID {file_id}.")
        return None

    # Iterate through all available download links
    for link in download_links:
        download_url = link.get('URI')
        if not download_url:
            continue
        try:
            logging.info(f"Attempting to download from {download_url}")
            download_response = session.get(download_url, stream=True)
            download_response.raise_for_status()
            file_path = os.path.join(mod_download_dir, file_name)
            with open(file_path, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"Successfully downloaded {file_name} for mod ID {mod_id}")
            return file_path
        except requests.HTTPError as e:
            logging.error(f"Failed to download from {download_url}: {e}")
            logging.info("Trying the next available download link...")
            time.sleep(1)  # Optional: Wait before retrying
            continue

    logging.error(f"All download links failed for mod ID {mod_id}, file ID {file_id}.")
    return None

def prepare_package(mod_info, file_path, mod_entry):
    mod_name = mod_info.get('name', 'unknown_mod').replace(' ', '_')
    version = mod_info.get('version', 'unknown_version')
    description = mod_info.get('summary', 'No description provided.')
    website_url = mod_info.get('url', '')
    package_name = f"{mod_name}_{version}"
    package_path = os.path.join('packages', package_name)
    os.makedirs(package_path, exist_ok=True)

    # Extract the downloaded mod file into the package directory
    try:
        shutil.unpack_archive(file_path, package_path)
        logging.info(f"Extracted {file_path} to {package_path}.")
    except Exception as e:
        logging.error(f"Failed to unpack archive {file_path}: {e}")
        return None

    # Create required files
    create_manifest(package_path, mod_name, version, description, [], website_url)
    create_readme(package_path, mod_info)
    create_changelog(package_path, mod_info)
    create_icon(package_path)

    # Zip the package
    package_zip = f"{package_path}.zip"
    zip_directory(package_path, package_zip)
    logging.info(f"Packaged mod into {package_zip}.")

    return package_zip

def create_manifest(package_path, mod_name, version, description, dependencies, website_url):
    manifest = {
        "name": mod_name,
        "version_number": version,
        "website_url": website_url,
        "description": description,
        "dependencies": dependencies
    }
    manifest_path = os.path.join(package_path, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=4)
    logging.info(f"Created manifest.json at {manifest_path}.")

def create_readme(package_path, mod_info):
    readme_content = f"# {mod_info.get('name', 'Unknown Mod')}\n\n{mod_info.get('description', '')}\n"
    readme_path = os.path.join(package_path, 'README.md')
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    logging.info(f"Created README.md at {readme_path}.")

def create_changelog(package_path, mod_info):
    changelog_content = f"## Version {mod_info.get('version', 'unknown')} - {datetime.now().date()}\n\n- Automated update.\n"
    changelog_path = os.path.join(package_path, 'CHANGELOG.md')
    with open(changelog_path, 'w') as f:
        f.write(changelog_content)
    logging.info(f"Created CHANGELOG.md at {changelog_path}.")

def create_icon(package_path):
    icon_path = os.path.join(package_path, 'icon.png')
    if os.path.exists('default_icon.png'):
        shutil.copyfile('default_icon.png', icon_path)
        logging.info(f"Copied default_icon.png to {icon_path}.")
    else:
        # Create a blank icon.png as a placeholder
        try:
            from PIL import Image
            img = Image.new('RGBA', (256, 256), color = (73, 109, 137))
            img.save(icon_path)
            logging.info(f"Created placeholder icon.png at {icon_path}.")
        except ImportError:
            logging.warning("Pillow library not installed. Cannot create icon.png.")

def zip_directory(folder_path, zip_path):
    shutil.make_archive(zip_path.replace('.zip', ''), 'zip', folder_path)
    logging.info(f"Zipped {folder_path} into {zip_path}.")

def upload_to_thunderstore(package_zip, thunderstore_game_domain):
    try:
        with open(package_zip, 'rb') as f:
            files = {'file': f}
            url = f'https://thunderstore.io/api/v1/package/upload/'
            response = requests.post(url, headers=THUNDERSTORE_HEADERS, files=files)
            response.raise_for_status()
            logging.info(f"Uploaded {package_zip} to Thunderstore.")
            return response.json()
    except requests.HTTPError as e:
        logging.error(f"Failed to upload {package_zip} to Thunderstore: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error during upload: {e}")
        raise

def generate_report(mods_processed):
    report_lines = []
    for mod in mods_processed:
        status = mod.get('status', 'Unknown')
        mod_id = mod['mod_id']
        name = mod.get('name', 'N/A')
        version = mod.get('version', 'N/A')
        report_lines.append(f"Mod ID: {mod_id}, Name: {name}, Version: {version}, Status: {status}")
    report_content = "\n".join(report_lines)
    print("Processing Report:")
    print(report_content)
    logging.info("Processing Report:")
    logging.info(report_content)

def main():
    os.makedirs('downloads', exist_ok=True)
    os.makedirs('packages', exist_ok=True)

    mod_list_data = load_mod_list('mods.json')
    nexus_game_domain = mod_list_data.get('nexus_game_domain')
    thunderstore_game_domain = mod_list_data.get('thunderstore_game_domain')
    mods = mod_list_data.get('mods', [])

    if not nexus_game_domain or not thunderstore_game_domain:
        logging.error("nexus_game_domain and/or thunderstore_game_domain not set in mods.json.")
        exit(1)

    mods_processed = []

    for mod_entry in mods:
        mod_data = {'mod_id': mod_entry['mod_id'], 'name': mod_entry.get('name')}
        mod_id = mod_entry['mod_id']
        try:
            logging.info(f"Processing mod ID: {mod_id}")
            mod_info = get_mod_info(mod_id, nexus_game_domain)

            if not is_new_version(mod_info, mod_entry):
                mod_data['version'] = mod_info.get('version', 'N/A')
                mod_data['status'] = 'Up-to-date'
                mods_processed.append(mod_data)
                continue

            latest_file = get_latest_file_info(mod_id, nexus_game_domain)
            if not latest_file:
                mod_data['status'] = 'No files found'
                mods_processed.append(mod_data)
                continue

            file_id = latest_file['file_id']
            file_name = latest_file['file_name']

            mod_download_dir = os.path.join('downloads', str(mod_id))
            os.makedirs(mod_download_dir, exist_ok=True)

            logging.info(f"Downloading mod '{mod_info.get('name', 'Unknown')}' version {mod_info.get('version', 'unknown')}")
            file_path = download_mod_file(mod_id, file_id, file_name, mod_download_dir, nexus_game_domain)
            if not file_path:
                mod_data['status'] = 'Download failed'
                mods_processed.append(mod_data)
                continue

            logging.info("Preparing package for Thunderstore...")
            package_zip = prepare_package(mod_info, file_path, mod_entry)
            if not package_zip:
                mod_data['status'] = 'Packaging failed'
                mods_processed.append(mod_data)
                continue

            logging.info("Uploading package to Thunderstore...")
            upload_response = upload_to_thunderstore(package_zip, thunderstore_game_domain)
            package_url = upload_response.get('package_url', 'URL not provided')
            logging.info(f"Successfully uploaded: {package_url}")

            mod_data['version'] = mod_info.get('version', 'N/A')
            mod_data['status'] = 'Success'
            # Update last processed version
            mod_entry['last_processed_version'] = mod_info.get('version', 'N/A')
        except Exception as e:
            logging.error(f"An error occurred with mod ID {mod_id}: {e}")
            mod_data['status'] = f"Failed: {e}"
        mods_processed.append(mod_data)

    # Save the updated mod list only after processing
    save_mod_list(mod_list_data, 'mods.json')

    # Generate a report
    generate_report(mods_processed)
    logging.info("Processing complete.")

if __name__ == '__main__':
    main()
