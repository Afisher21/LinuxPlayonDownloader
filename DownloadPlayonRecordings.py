#!/usr/bin/env python3
#-*- coding: utf-8 -*-

#
#   PlayonCloud recorder
#
# update-alternatives --install /usr/bin/python python /usr/bin/python3.7 2
# sudo apt-get install chromium-chromedriver
# sudo apt-get install libxml2-dev libxslt-dev python-dev
# which python3 (make sure that path is /usr/bin/python3)
#
# Finally: crontab -e => 0 23 * * * /usr/bin/python3 /plex/media/Media/DownloadPlayonRecordings.py
#   a.k.a. automatically run every day at 11:00 p.m.
#
# For bonus points, setup playon to automatically update:
#  bash -c "$(wget -qO - https://raw.githubusercontent.com/mrworf/plexupdate/master/extras/installer.sh)"

from cfg import *

logging.basicConfig(filename=os.path.join(g_paths['mediaroot'], g_settings['logfile']), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a second logger for printing to Console simultaneously
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

from PlayonVideo import *
import DriverHelpers as dh
import FilesystemHelpers as fsh

def main():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import subprocess
    
    # Some modules (looking at you webdriver) are exceptionally noisy for debug purposes
    #  this sets them to only log if warning or higher
    for log_name, log_obj in logging.Logger.manager.loggerDict.items():
        if log_name != __name__:
            logging.getLogger(log_name).setLevel(logging.WARNING)
    
    driver = {}
    # Add options to allow the driver to operate in headless mode without a GUI. Required since most
    #  of the time a raspbian server isn't running a GUI anyways
    options = Options()
    options.headless = True
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.experimental_options['prefs'] = {'download.default_directory': g_paths['downloadfolder']}
    
    try:
        driver = webdriver.Chrome(options = options)
    except:
        driver = webdriver.Chrome(g_paths['chromewebdriver'], options = options)

    try:
        logging.info('Webdriver created, attempting to log in to Playon recorder. This can take a few minutes some times.')
        dh.LogInToPlayon(driver)

        dl = dh.CheckForNewVideos(driver)
        if len(dl) > 0:
            dh.DownloadVideos(driver, dl)
            fsh.WaitForDownloads(driver, dl, True)
            fsh.MoveDownloadsToPlayonFolder(dl)
            # Eventually playon will pickup these changes.. but why wait?
            subprocess.run([g_paths['mediascanner'], '--scan'])
            logging.info('Finished sucessfully! Just need to cleanup')
        else:
            logging.info('No videos to download today.')
    except:
        logging.error('Some kind of fatal exception caught by main!')

    finally:
        driver.close()
    

if __name__ == '__main__':
    #dl = GenerateDownloadList()
    #MoveDownloadsToPlayonFolder(dl)
    main()
