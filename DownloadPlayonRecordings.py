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

from genericpath import exists
import logging, os, configparser

g_iniPath = 'PlayonDownloader.ini'

# ExtendedInterpolation means ini can use ${} instead of %()s, and lets you refer to other sections besides default if needed
g_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
g_config.read(g_iniPath)

g_paths = g_config['Paths']
g_creds = g_config['Credentials']
g_settings = g_config['Settings']

install_requires = [
    'beautifulsoup4',
    'IMDbPY',
    'selenium'
]

logging.basicConfig(filename=os.path.join(g_paths['mediaroot'], g_settings['logfile']), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

from PlayonVideo import PlayonVideo
from DriverHelpers import *
from FilesystemHelpers import *

def main():
    from selenium import webdriver
    import subprocess
    
    # Some modules (looking at you webdriver) are exceptionally noisy for debug purposes
    #  this sets them to only log if warning or higher
    for log_name, log_obj in logging.Logger.manager.loggerDict.items():
        if log_name != __name__:
            logging.getLogger(log_name).setLevel(logging.WARNING)
    
    driver = {}
    try:
        driver = webdriver.Chrome()
    except:
        driver = webdriver.Chrome(g_paths['chromewebdriver'])

    try:
        LogInToPlayon(driver)

        dl = CheckForNewVideos(driver)
        if len(dl) > 0:
            DownloadVideos(driver, dl)
            WaitForDownloads(driver, dl, True)
            MoveDownloadsToPlayonFolder(dl)
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