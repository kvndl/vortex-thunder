# src/uploader.py

import requests
import logging

class Uploader:
    def __init__(self, thunderstore_api_key):
        self.thunderstore_api_key = thunderstore_api_key
        self.headers = {
            'Authorization': f'Bearer {self.thunderstore_api_key}'
        }
    
    def upload_to_thunderstore(self, package_zip, team_name, categories):
        """
        Uploads the packaged mod to Thunderstore with specified team and categories.
        
        Args:
            package_zip (str): Path to the zipped mod package.
            team_name (str): The team name on Thunderstore (e.g., "community").
            categories (list): List of categories for the mod.
        
        Returns:
            dict or None: Response JSON if successful, else None.
        """
        upload_url = 'https://thunderstore.io/api/v1/package/upload/'
        try:
            with open(package_zip, 'rb') as f:
                files = {'file': f}
                # Prepare additional data
                data = {
                    'team': team_name,
                    'categories': ','.join(categories)  # Assuming Thunderstore expects comma-separated categories
                }
                response = requests.post(upload_url, headers=self.headers, files=files, data=data)
                if response.status_code == 403:
                    logging.error(f"403 Forbidden when uploading {package_zip} to Thunderstore. Check your API key.")
                    return None
                response.raise_for_status()
                logging.info(f"Uploaded {package_zip} to Thunderstore successfully.")
                return response.json()
        except requests.HTTPError as e:
            logging.error(f"HTTP error occurred while uploading {package_zip}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error occurred while uploading {package_zip}: {e}")
            return None
