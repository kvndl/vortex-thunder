import os
import sys
import argparse
import logging
import requests

from src.logger import setup_logging
from src.config import Config
from src.downloader import Downloader
from src.uploader import Uploader
from src.utils import create_placeholder_icon, zip_directory, sanitize_readme

def prepare_package(mod_info, file_path, mod_entry, nexus_game_domain, all_mods):
    """
    Prepares the mod package for Thunderstore by extracting, creating necessary files, and zipping.
    Handles dynamic dependencies by fetching their latest versions.
    """
    import shutil
    import zipfile
    from datetime import datetime

    mod_name = mod_info.get('name', 'unknown_mod').replace(' ', '_')
    version = mod_info.get('version', 'unknown_version')
    description = mod_info.get('summary', 'No description provided.')
    # Dynamically generate the Nexus Mods URL
    website_url = f"https://www.nexusmods.com/{nexus_game_domain}/mods/{mod_info.get('mod_id')}"
    package_name = f"{mod_name}_{version}"
    package_path = os.path.join('packages', package_name)
    os.makedirs(package_path, exist_ok=True)

    # Extract the downloaded mod file into the package directory
    try:
        shutil.unpack_archive(file_path, package_path)
        logging.info(f"Extracted {file_path} to {package_path}")
    except zipfile.BadZipFile:
        logging.error(f"The file {file_path} is not a valid zip archive.")
        return None
    except Exception as e:
        logging.error(f"Failed to unpack archive {file_path}: {e}")
        return None

    # Retrieve dependencies from mod_entry and format them
    raw_dependencies = mod_entry.get('dependencies', [])
    formatted_dependencies = []
    for dep_name in raw_dependencies:
        # Find the dependency mod entry by name
        dep_entry = next((mod for mod in all_mods if mod['name'] == dep_name), None)
        if dep_entry and dep_entry.get('last_processed_version'):
            dep_author = "UnknownAuthor"  # Replace with actual author retrieval if available
            # If author information is available in mod_info, use it
            dep_mod_info = downloader.get_mod_info(dep_entry['mod_id'])
            if dep_mod_info and dep_mod_info.get('author'):
                dep_author = dep_mod_info.get('author')
            dep_version = dep_entry.get('last_processed_version')
            formatted_dependency = f"{dep_author}-{dep_name}-{dep_version}"
            formatted_dependencies.append(formatted_dependency)
        else:
            logging.warning(f"Dependency '{dep_name}' for mod '{mod_info.get('name')}' not found or not processed yet.")
            # Optionally, you can choose to skip or halt the process
            # For now, we'll skip adding this dependency
            continue

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

def create_manifest(package_path, mod_name, version, description, dependencies, website_url):
    """
    Creates a manifest.json file for the mod package.
    """
    import json
    import logging

    manifest = {
        "name": mod_name,
        "version_number": version,
        "website_url": website_url,
        "description": description,
        "dependencies": dependencies  # Added dependencies here
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
    import logging

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
    import logging
    from datetime import datetime

    changelog_content = f"## Version {mod_info.get('version', 'unknown')} - {datetime.now().date()}\n\n- Automated update.\n"
    changelog_path = os.path.join(package_path, 'CHANGELOG.md')
    try:
        with open(changelog_path, 'w') as f:
            f.write(changelog_content)
        logging.info(f"Created CHANGELOG.md at {changelog_path}")
    except Exception as e:
        logging.error(f"Failed to create CHANGELOG.md at {changelog_path}: {e}")

def generate_report(mods_processed):
    """
    Generates a processing report.
    """
    report_lines = []
    for mod in mods_processed:
        status = mod.get('status', 'Unknown')
        mod_id = mod['mod_id']
        name = mod.get('name', 'N/A')
        version = mod.get('version', 'N/A')
        report_lines.append(f"Mod ID: {mod_id}, Name: {name}, Version: {version}, Status: {status}")
    report_content = "\n".join(report_lines)
    print("\nProcessing Report:")
    print(report_content)

def download_mods(config, downloader):
    """
    Handles the downloading of mods.
    """
    mods = config.get_mods()
    if not mods:
        logging.error("No mods found in configuration.")
        return []
    
    mods_processed = []
    
    for mod_entry in mods:
        mod_data = {'mod_id': mod_entry['mod_id'], 'name': mod_entry.get('name')}
        mod_id = mod_entry['mod_id']
        try:
            logging.info(f"Processing mod ID: {mod_id}")
            mod_info = downloader.get_mod_info(mod_id)
            
            if not mod_info:
                mod_data['status'] = 'Failed to retrieve mod info'
                mods_processed.append(mod_data)
                continue

            if not downloader.is_new_version(mod_info, mod_entry):
                logging.info(f"No new version for mod ID {mod_id}. Skipping.")
                mod_data['version'] = mod_info.get('version', 'N/A')
                mod_data['status'] = 'Up-to-date'
                mods_processed.append(mod_data)
                continue

            latest_file = downloader.get_latest_file_info(mod_id)
            if not latest_file:
                logging.warning(f"No files found for mod ID {mod_id}. Skipping.")
                mod_data['status'] = 'No files found'
                mods_processed.append(mod_data)
                continue

            file_id = latest_file['file_id']
            file_name = latest_file['file_name']

            mod_download_dir = os.path.join('downloads', str(mod_id))
            os.makedirs(mod_download_dir, exist_ok=True)

            logging.info(f"Downloading mod '{mod_info.get('name', 'Unknown')}' version {mod_info.get('version', 'unknown')}")
            file_path = downloader.download_mod_file(mod_id, file_id, file_name, mod_download_dir)
            if not file_path:
                mod_data['status'] = 'Download failed'
                mods_processed.append(mod_data)
                continue

            # Prepare package with dynamic dependencies
            package_zip = prepare_package(mod_info, file_path, mod_entry, config.get_game_domains()[0], mods)
            if not package_zip:
                mod_data['status'] = 'Packaging failed'
                mods_processed.append(mod_data)
                continue

            # Update last_processed_version only after successful download and packaging
            mod_entry['last_processed_version'] = mod_info.get('version', 'N/A')
            mod_data['version'] = mod_info.get('version', 'N/A')
            mod_data['status'] = 'Downloaded and packaged'
            mods_processed.append(mod_data)

        except Exception as e:
            logging.error(f"An unexpected error occurred with mod ID {mod_id}: {e}")
            mod_data['status'] = f"Failed: {e}"
            mods_processed.append(mod_data)
    
    # Save the updated mod list after downloading
    config.save_config()
    
    return mods_processed

def upload_mods(config, uploader):
    """
    Handles the uploading of mods to Thunderstore.
    """
    mods = config.get_mods()
    if not mods:
        logging.error("No mods found in configuration.")
        return []
    
    mods_processed = []
    
    for mod_entry in mods:
        mod_data = {'mod_id': mod_entry['mod_id'], 'name': mod_entry.get('name')}
        mod_id = mod_entry['mod_id']
        try:
            version = mod_entry.get('last_processed_version')
            if not version:
                logging.info(f"No processed version for mod ID {mod_id}. Skipping upload.")
                mod_data['status'] = 'No processed version'
                mods_processed.append(mod_data)
                continue
            
            mod_name = mod_entry.get('name', 'unknown_mod').replace(' ', '_')
            package_zip = os.path.join('packages', f"{mod_name}_{version}.zip")
            if not os.path.exists(package_zip):
                logging.error(f"Package {package_zip} does not exist. Skipping upload.")
                mod_data['status'] = 'Package not found'
                mods_processed.append(mod_data)
                continue
            
            # Retrieve the specific mod's categories
            categories = mod_entry.get('categories', [])
            if not categories:
                logging.warning(f"No categories specified for mod '{mod_name}'. Using default categories.")
                categories = ["Misc"]  # Default category if none specified
            
            logging.info(f"Uploading package {package_zip} to Thunderstore.")
            upload_response = uploader.upload_to_thunderstore(package_zip, config.data.get('team_name', 'community'), categories)
            if upload_response:
                logging.info(f"Successfully uploaded: {upload_response.get('package_url', 'URL not provided')}")
                mod_data['version'] = version
                mod_data['status'] = 'Uploaded'
            else:
                logging.error(f"Failed to upload {package_zip} to Thunderstore.")
                mod_data['status'] = 'Upload failed'
            mods_processed.append(mod_data)
        
        except Exception as e:
            logging.error(f"An unexpected error occurred while uploading mod ID {mod_id}: {e}")
            mod_data['status'] = f"Failed: {e}"
            mods_processed.append(mod_data)
    
    # Save the updated mod list after uploading
    config.save_config()
    
    return mods_processed

def run_all(config, downloader, uploader):
    """
    Runs the download and upload processes sequentially.
    """
    logging.info("Starting download process...")
    downloaded_mods = download_mods(config, downloader)
    
    logging.info("Starting upload process...")
    uploaded_mods = upload_mods(config, uploader)
    
    # Combine both reports
    combined_report = downloaded_mods + uploaded_mods
    generate_report(combined_report)

def main():
    """
    The main entry point for the CLI application.
    """
    setup_logging()
    
    parser = argparse.ArgumentParser(description="vortex-thunder: Download mods from Nexus Mods and upload to Thunderstore.")
    subparsers = parser.add_subparsers(dest='command', help='Sub-commands')
    
    # Download sub-command
    download_parser = subparsers.add_parser('download', help='Download mods from Nexus Mods.')
    
    # Upload sub-command
    upload_parser = subparsers.add_parser('upload', help='Upload mods to Thunderstore.')
    
    # Run sub-command
    run_parser = subparsers.add_parser('run', help='Download and upload mods sequentially.')
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = Config()
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    try:
        nexus_game_domain, thunderstore_game_domain, game_id = config.get_game_domains()
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Initialize a requests.Session
    session = requests.Session()
    session.headers.update({
        'apikey': os.getenv('NEXUS_API_KEY'),
        'Accept': 'application/json',
        'User-Agent': 'vortex-thunder/1.0 (admin@kvndl.xyz)',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://www.nexusmods.com'
    })
    
    # Check for Nexus API key
    nexus_api_key = os.getenv('NEXUS_API_KEY')
    if not nexus_api_key:
        logging.error("NEXUS_API_KEY not set. Please set it as an environment variable.")
        sys.exit(1)
    
    # Fetch and set session cookies from browser_cookie3
    from src.downloader import Downloader
    from src.uploader import Uploader

    try:
        import browser_cookie3
        # Fetch cookies from Firefox
        cj_firefox = browser_cookie3.firefox(domain_name='nexusmods.com')
        for cookie in cj_firefox:
            session.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
        logging.info("Cookies from Firefox have been set.")
    except Exception as e:
        logging.warning(f"Failed to fetch Firefox cookies: {e}")
    
    try:
        # Fetch cookies from Chromium-based browsers
        cj_chrome = browser_cookie3.chrome(domain_name='nexusmods.com')
        for cookie in cj_chrome:
            session.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
        logging.info("Cookies from Chromium have been set.")
    except Exception as e:
        logging.warning(f"Failed to fetch Chromium cookies: {e}")
    
    # Initialize Downloader with session
    downloader = Downloader(session=session, nexus_game_domain=nexus_game_domain, game_id=game_id)
    
    # Initialize Uploader with Thunderstore API key
    thunderstore_api_key = os.getenv('THUNDERSTORE_API_KEY')
    if not thunderstore_api_key:
        logging.error("THUNDERSTORE_API_KEY not set. Please set it as an environment variable.")
        sys.exit(1)
    
    uploader = Uploader(thunderstore_api_key)
    
    if args.command == 'download':
        mods_processed = download_mods(config, downloader)
        generate_report(mods_processed)
    elif args.command == 'upload':
        mods_processed = upload_mods(config, uploader)
        generate_report(mods_processed)
    elif args.command == 'run':
        run_all(config, downloader, uploader)
    else:
        # If no arguments are provided, default to 'run'
        logging.info("No subcommand provided. Running download and upload sequentially.")
        run_all(config, downloader, uploader)

if __name__ == '__main__':
    main()
