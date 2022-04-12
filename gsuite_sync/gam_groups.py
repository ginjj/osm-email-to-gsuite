import subprocess
import sys

gam_working_directory ='C:\GAMWork'
dry_run = False # Set dry_run flag to print GAM commands without executing

def gam_sync_group(group_name, email_address_set):
    # GAMADV-XTD3 setup for VS Code shell requires the follwing environment variables to be added to settings.json
    # 'GAMCFGDIR': 'C:\\GAMConfig', 'PATH': 'C:\\GAMADV-XTD3\\' and working directory 
    # see https://github.com/taers232c/GAMADV-XTD3/wiki/How-to-Install-Advanced-GAM   
    # usage 'gam update group group_name sync 'email1 email2 ...'
    gam_command = 'gam update group ' + group_name + ' sync "' + ' '.join(email_address_set) +'"'
    print('Synchronising', group_name, 'group with', len(email_address_set), 'email addresses from OSM')
    if not dry_run:
        try:
            subprocess.run(gam_command, cwd=gam_working_directory, check=True)
        except subprocess.CalledProcessError as exc:                                                                                                   
            print('GAMADV-XTD3 error code:', exc.returncode, exc.output)
            sys.exit('Error when running sub-process GAMADV-XTD3 command')
    else:
        print("DRYRUN:",gam_command)
    print('Sucsessfully completed synchronising group\n')