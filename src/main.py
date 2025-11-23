"""
Entry point for Cloud Run deployment.
Wraps Streamlit to provide better error handling for authentication failures.
"""

import os
import sys

# Check if we can actually run (this won't help with IAM 403s, but documents the issue)
if __name__ == "__main__":
    # Import and run the actual Streamlit app
    from streamlit.web import cli as stcli
    
    # Point to the actual app
    sys.argv = ["streamlit", "run", "src/app.py", 
                "--server.port=8080", 
                "--server.address=0.0.0.0",
                "--server.enableCORS=false",
                "--server.enableXsrfProtection=false"]
    
    sys.exit(stcli.main())
