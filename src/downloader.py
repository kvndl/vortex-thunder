# src/downloader.py

import os
import requests
import logging
import time
import json

class Downloader:
    def __init__(self, session, nexus_game_domain, game_id):
        self.session = session
        self.nexus_game_domain = nexus_game_domain
        self.game_id = game_id
    
    def get_mod_info(self, mod_id):
        """
        Retrieves mod information from Nexus Mods API.
        """
        url = f'https://api.nexusmods.com/v1/games/{self.nexus_game_domain}/mods/{mod_id}.json'
        try:
            response = self.session.get(url)
            if response.status_code == 403:
                logging.error(f"403 Forbidden when accessing mod ID {mod_id}. Check your API key and session cookies.")
                return None
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logging.error(f"HTTP error occurred while fetching mod info for mod ID {mod_id}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error occurred while fetching mod info for mod ID {mod_id}: {e}")
            return None
    
    def get_latest_file_info(self, mod_id):
        """
        Retrieves the latest file information for a mod.
        """
        url = f'https://api.nexusmods.com/v1/games/{self.nexus_game_domain}/mods/{mod_id}/files.json'
        for attempt in range(3):  # Limit to 3 attempts
            try:
                response = self.session.get(url)
                if response.status_code == 403:
                    logging.error(f"403 Forbidden when accessing files for mod ID {mod_id}. Check your API key and session cookies.")
                    return None
                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', '60'))
                    logging.warning(f"Rate limited when accessing files for mod ID {mod_id}. Retrying after {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                files = response.json().get('files', [])
                if not files:
                    logging.warning(f"No files found for mod ID {mod_id}.")
                    return None
                # Select the most recently uploaded file
                latest_file = max(files, key=lambda x: x.get('uploaded_timestamp', ''))
                return latest_file
            except requests.HTTPError as e:
                logging.error(f"HTTP error occurred while fetching files for mod ID {mod_id}: {e}")
                return None
            except Exception as e:
                logging.error(f"Unexpected error occurred while fetching files for mod ID {mod_id}: {e}")
                return None
        logging.error(f"Failed to retrieve file info for mod ID {mod_id} after multiple attempts.")
        return None

    def is_new_version(self, mod_info, mod_entry):
        """
        Determines if the mod has a new version.
        """
        current_version = mod_info.get('version')
        last_version = mod_entry.get('last_processed_version')
        return current_version != last_version

    def download_mod_file(self, mod_id, file_id, file_name, mod_download_dir):
        """
        Downloads the mod file from Nexus Mods.
        """
        # URL to generate the download link
        url = 'https://www.nexusmods.com/Core/Libs/Common/Managers/Downloads?GenerateDownloadUrl'
        
        # Set the 'Referer' header dynamically based on the mod's files tab
        referer_url = f'https://www.nexusmods.com/{self.nexus_game_domain}/mods/{mod_id}?tab=files&file_id={file_id}'
        
        # Prepare headers specific to this request
        headers = {
            'Referer': referer_url,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://www.nexusmods.com',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # Prepare the POST data
        data = {
            'fid': file_id,
            'game_id': self.game_id
        }
        
        try:
            # Make the POST request to get the download URL
            response = self.session.post(url, headers=headers, data=data)
            if response.status_code == 403:
                logging.error(f"403 Forbidden when generating download URL for mod ID {mod_id} file ID {file_id}.")
                return None
            response.raise_for_status()
        except requests.HTTPError as e:
            logging.error(f"Failed to get download link for mod ID {mod_id} file ID {file_id}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error when getting download link for mod ID {mod_id} file ID {file_id}: {e}")
            return None
        
        # Parse the JSON response to get the download URL
        try:
            download_info = response.json()
            download_url = download_info.get('url')
            if not download_url:
                logging.error(f"No download URL found in response for mod ID {mod_id} file ID {file_id}.")
                return None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response for mod ID {mod_id} file ID {file_id}: {e}")
            return None
        
        # Attempt to download the file
        try:
            logging.info(f"Attempting to download from {download_url}")
            download_response = self.session.get(download_url, stream=True)
            if download_response.status_code == 403:
                logging.error(f"403 Forbidden when downloading mod ID {mod_id} from {download_url}.")
                return None
            download_response.raise_for_status()
            file_path = os.path.join(mod_download_dir, file_name)
            with open(file_path, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"Successfully downloaded {file_name} for mod ID {mod_id}")
            return file_path
        except requests.HTTPError as e:
            logging.error(f"Failed to download from {download_url}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error occurred while downloading {file_name} for mod ID {mod_id}: {e}")
            return None
