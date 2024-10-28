# src/config.py

import json
import logging

class Config:
    def __init__(self, filename='mods.json'):
        self.filename = filename
        self.data = self.load_config()
    
    def load_config(self):
        """
        Loads the configuration from a JSON file.
        """
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
            logging.info(f"Loaded configuration from {self.filename}.")
            return data
        except FileNotFoundError:
            logging.error(f"Configuration file {self.filename} not found.")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing {self.filename}: {e}")
            raise
    
    def save_config(self):
        """
        Saves the current configuration to a JSON file.
        """
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=4)
            logging.info(f"Saved configuration to {self.filename}.")
        except Exception as e:
            logging.error(f"Failed to save configuration to {self.filename}: {e}")
    
    def get_game_domains(self):
        """
        Retrieves game domains from the configuration.
        """
        nexus_game_domain = self.data.get('nexus_game_domain')
        thunderstore_game_domain = self.data.get('thunderstore_game_domain')
        game_id = self.data.get('game_id')
        
        if not all([nexus_game_domain, thunderstore_game_domain, game_id]):
            logging.error("nexus_game_domain, thunderstore_game_domain, and game_id must be set in mods.json.")
            raise ValueError("Incomplete configuration.")
        
        return nexus_game_domain, thunderstore_game_domain, game_id
    
    def get_mods(self):
        """
        Retrieves the list of mods from the configuration.
        """
        return self.data.get('mods', [])
