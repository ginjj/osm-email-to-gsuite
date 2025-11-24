"""
Entry point for Cloud Run deployment.
Starts either Streamlit UI or Flask API based on APP_MODE environment variable.
"""

import os
import sys

def main():
    """Main entry point - chooses between UI and API mode."""
    mode = os.getenv('APP_MODE', 'ui')
    
    if mode == 'api':
        # Run Flask API for Cloud Scheduler
        print("Starting Flask API server...")
        from api import app
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
    else:
        # Run Streamlit UI (default)
        print("Starting Streamlit UI...")
        from streamlit.web import cli as stcli
        
        # Point to the actual app
        sys.argv = ["streamlit", "run", "src/app.py", 
                    f"--server.port={os.getenv('PORT', '8080')}", 
                    "--server.address=0.0.0.0",
                    "--server.enableCORS=false",
                    "--server.enableXsrfProtection=false"]
        
        sys.exit(stcli.main())


if __name__ == "__main__":
    main()

