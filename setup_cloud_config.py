"""
Setup script for deploying configuration to Google Cloud.
Run this once to upload configs to Secret Manager and Cloud Storage.
"""

import argparse
import yaml
from google.cloud import secretmanager
from google.cloud import storage


def create_secret(project_id: str, secret_id: str, data: str):
    """Create or update a secret in Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"
    
    # Try to create the secret
    try:
        secret = client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        print(f"✅ Created secret: {secret.name}")
    except Exception as e:
        if "already exists" in str(e):
            print(f"ℹ️  Secret {secret_id} already exists, will add new version")
        else:
            raise
    
    # Add secret version with data
    secret_path = f"{parent}/secrets/{secret_id}"
    version = client.add_secret_version(
        request={
            "parent": secret_path,
            "payload": {"data": data.encode('UTF-8')},
        }
    )
    print(f"✅ Added secret version: {version.name}")


def upload_to_bucket(project_id: str, bucket_name: str, file_path: str, blob_name: str):
    """Upload a file to Cloud Storage bucket."""
    client = storage.Client(project=project_id)
    
    # Create bucket if it doesn't exist
    try:
        bucket = client.bucket(bucket_name)
        if not bucket.exists():
            bucket = client.create_bucket(bucket_name, location="us-central1")
            print(f"✅ Created bucket: {bucket_name}")
        else:
            print(f"ℹ️  Bucket {bucket_name} already exists")
    except Exception as e:
        print(f"⚠️  Bucket check/create: {e}")
        bucket = client.bucket(bucket_name)
    
    # Upload file
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(file_path, content_type='text/yaml')
    print(f"✅ Uploaded {file_path} to gs://{bucket_name}/{blob_name}")


def main():
    parser = argparse.ArgumentParser(description='Setup OSM sync configuration in Google Cloud')
    parser.add_argument('--project-id', required=True, help='GCP Project ID')
    parser.add_argument('--bucket-name', required=True, help='Cloud Storage bucket name for email_config.yaml')
    parser.add_argument('--osm-config', default='osm_config.yaml', help='Path to osm_config.yaml')
    parser.add_argument('--google-config', default='google_config.yaml', help='Path to google_config.yaml')
    parser.add_argument('--email-config', default='email_config.yaml', help='Path to email_config.yaml')
    
    args = parser.parse_args()
    
    print(f"\n🚀 Setting up configuration for project: {args.project_id}\n")
    
    # 1. Upload OSM config to Secret Manager
    print("📝 Step 1: Uploading osm_config.yaml to Secret Manager...")
    try:
        with open(args.osm_config, 'r') as f:
            osm_data = f.read()
        create_secret(args.project_id, 'osm-config', osm_data)
    except Exception as e:
        print(f"❌ Failed to upload osm_config: {e}")
        return
    
    # 2. Upload Google config to Secret Manager
    print("\n📝 Step 2: Uploading google_config.yaml to Secret Manager...")
    try:
        with open(args.google_config, 'r') as f:
            google_data = f.read()
        create_secret(args.project_id, 'google-config', google_data)
    except Exception as e:
        print(f"❌ Failed to upload google_config: {e}")
        return
    
    # 3. Upload email config to Cloud Storage
    print(f"\n📝 Step 3: Uploading email_config.yaml to Cloud Storage bucket...")
    try:
        upload_to_bucket(args.project_id, args.bucket_name, args.email_config, 'email_config.yaml')
    except Exception as e:
        print(f"❌ Failed to upload email_config: {e}")
        return
    
    print("\n✅ Configuration setup complete!")
    print(f"\n📋 Next steps:")
    print(f"   1. Set environment variables in Cloud Run:")
    print(f"      - GCP_PROJECT_ID={args.project_id}")
    print(f"      - CONFIG_BUCKET_NAME={args.bucket_name}")
    print(f"      - USE_CLOUD_CONFIG=true")
    print(f"   2. Deploy your application to Cloud Run")
    print(f"   3. Grant Cloud Run service account permissions:")
    print(f"      - Secret Manager Secret Accessor (for secrets)")
    print(f"      - Storage Object Admin (for bucket)")
    

if __name__ == '__main__':
    main()
