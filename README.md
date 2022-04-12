# osm-email-to-gsuite

Set of scripts to pull member information from Online Scout Manager and:
- Synchronise to Google Workspace using GAM (oms_to_gsuite.py)*
- Export current term members to CSV (oms_to_csv.py)
- Export section attendance history to CSV (oms_to_csv_history.py)



An API key is required for access to Online Scout Manager (https://onlinescoutmanager.co.uk Settings / My Account Details / Developer Tools) to be stored in osm_config.yaml

### oms_to_gsuite.py

Google Workspace Group email address prefixes and corresponding OSM sectionids details are required in email_config.yaml. The sectionid can be fouund by using the Chrome developer tools (F12) under Network / Payload when loading a section page in OSM.      


\*To synchronise to Google Workspace using GAMADV-XTD3 (see https://github.com/taers232c/GAMADV-XTD3/wiki/How-to-Install-Advanced-GAM)
GAMADV-XTD3 setup for VS Code shell requires the following environment variables to be added to settings.json
```
'GAMCFGDIR': 'C:\\GAMConfig', 'PATH': 'C:\\GAMADV-XTD3\\' [and working directory e.g. gam_working_directory ='C:\GAMWork'] 
```

