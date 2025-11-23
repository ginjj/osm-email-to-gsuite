"""
Configuration management for OSM sync application.
Handles loading configs from local files, Secret Manager, and Cloud Storage.
"""

import yaml
import os
from typing import Dict, Optional, Tuple
from google.cloud import secretmanager
from google.cloud import storage
from io import StringIO


class ConfigManager:
    """Manage application configuration from multiple sources."""
    
    def __init__(self, 
                 project_id: Optional[str] = None,
                 bucket_name: Optional[str] = None,
                 use_cloud: bool = False):
        """
        Initialize configuration manager.
        
        Args:
            project_id: GCP project ID (required if use_cloud=True)
            bucket_name: Cloud Storage bucket name for email_config.yaml
            use_cloud: If True, use Secret Manager and Cloud Storage. If False, use local files.
        """
        self.project_id = project_id or os.getenv('GCP_PROJECT_ID')
        self.bucket_name = bucket_name or os.getenv('CONFIG_BUCKET_NAME')
        self.use_cloud = use_cloud
        
        if self.use_cloud:
            if not self.project_id:
                raise ValueError("project_id required when use_cloud=True")
            self.secret_client = secretmanager.SecretManagerServiceClient()
            if self.bucket_name:
                self.storage_client = storage.Client(project=self.project_id)
                self.bucket = self.storage_client.bucket(self.bucket_name)
            else:
                self.storage_client = None
                self.bucket = None
    
    def _get_secret(self, secret_name: str) -> str:
        """Get secret value from Secret Manager."""
        name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
        response = self.secret_client.access_secret_version(request={"name": name})
        return response.payload.data.decode('UTF-8')
    
    def _load_yaml_from_string(self, yaml_string: str) -> Dict:
        """Parse YAML from string."""
        return yaml.safe_load(StringIO(yaml_string))
    
    def load_osm_config(self) -> Dict:
        """
        Load OSM API configuration.
        
        Returns:
            Dict with OSM API credentials
        """
        if self.use_cloud:
            # Load from Secret Manager
            secret_data = self._get_secret('osm-config')
            return self._load_yaml_from_string(secret_data)
        else:
            # Load from local file
            with open('config/osm_config.yaml', 'r') as f:
                return yaml.safe_load(f)
    
    def load_google_config(self) -> Dict:
        """
        Load Google Workspace configuration.
        
        Returns:
            Dict with Google Workspace settings
        """
        if self.use_cloud:
            # Load from Secret Manager
            secret_data = self._get_secret('google-config')
            return self._load_yaml_from_string(secret_data)
        else:
            # Load from local file
            with open('config/google_config.yaml', 'r') as f:
                return yaml.safe_load(f)
    
    def load_email_config(self) -> Dict:
        """
        Load email/section mapping configuration.
        
        Returns:
            Dict with section ID to email prefix mappings
        """
        if self.use_cloud and self.bucket:
            # Load from Cloud Storage
            blob = self.bucket.blob('email_config.yaml')
            if not blob.exists():
                raise FileNotFoundError(f"email_config.yaml not found in bucket {self.bucket_name}")
            yaml_content = blob.download_as_text()
            return self._load_yaml_from_string(yaml_content)
        else:
            # Load from local file
            with open('config/email_config.yaml', 'r') as f:
                return yaml.safe_load(f)
    
    def save_email_config(self, config: Dict) -> None:
        """
        Save email/section mapping configuration.
        
        Args:
            config: Section configuration dict to save
        """
        yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False)
        
        if self.use_cloud and self.bucket:
            # Save to Cloud Storage
            blob = self.bucket.blob('email_config.yaml')
            blob.upload_from_string(yaml_content, content_type='text/yaml')
        else:
            # Save to local file
            with open('config/email_config.yaml', 'w') as f:
                f.write(yaml_content)
    
    def load_all_configs(self) -> Tuple[Dict, Dict, Dict, Optional[str]]:
        """
        Load all configuration files.
        
        Returns:
            Tuple of (osm_config, google_config, email_config, error_message)
        """
        try:
            osm_config = self.load_osm_config()
            google_config = self.load_google_config()
            email_config = self.load_email_config()
            return osm_config, google_config, email_config, None
        except Exception as e:
            return None, None, None, str(e)
    
    def validate_email_config(self, config: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate email configuration structure.
        
        Args:
            config: Configuration dict to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(config, dict):
            return False, "Configuration must be a dictionary"
        
        if 'sections' not in config:
            return False, "Configuration must have 'sections' key"
        
        if not isinstance(config['sections'], list):
            return False, "'sections' must be a list"
        
        for i, section in enumerate(config['sections']):
            if not isinstance(section, dict):
                return False, f"Section {i} must be a dictionary"
            
            if 'id' not in section:
                return False, f"Section {i} missing 'id' field"
            
            if 'email' not in section:
                return False, f"Section {i} missing 'email' field"
            
            # Validate email prefix (alphanumeric only)
            email_prefix = section['email']
            if not email_prefix.replace('-', '').replace('_', '').isalnum():
                return False, f"Section {i} email prefix '{email_prefix}' contains invalid characters"
        
        return True, None


def get_config_manager() -> ConfigManager:
    """
    Get configured ConfigManager instance.
    
    Checks environment variables to determine if running in cloud or locally.
    """
    # Check if running in GCP (Cloud Run sets K_SERVICE env var)
    is_cloud = os.getenv('K_SERVICE') is not None or os.getenv('USE_CLOUD_CONFIG') == 'true'
    
    if is_cloud:
        project_id = os.getenv('GCP_PROJECT_ID')
        bucket_name = os.getenv('CONFIG_BUCKET_NAME')
        return ConfigManager(project_id=project_id, bucket_name=bucket_name, use_cloud=True)
    else:
        # Local development - use YAML files
        return ConfigManager(use_cloud=False)
