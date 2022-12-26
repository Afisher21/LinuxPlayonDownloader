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
# Finally: crontab -e => 0 23 * * * /usr/bin/python3 <repo path>/DownloadPlayonRecordings.py
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
    import subprocess
    try:
        driver = dh.PlayonWebdriver()
        logging.info('Webdriver created, attempting to log in to Playon recorder. This can take a few minutes some times.')
        driver.LogInToPlayon()

        dl = driver.CheckForNewVideos()
        if len(dl) > 0:
            driver.DownloadVideos(dl)
            fsh.WaitForDownloads(dl, True)
            fsh.MoveDownloadsToPlayonFolder(dl)
            # Eventually playon will pickup these changes.. but why wait?
            subprocess.run([g_paths['mediascanner'], '--scan'])
            logging.info('Finished sucessfully! Just need to cleanup')
        else:
            logging.info('No videos to download today.')
    except:
        logging.error('Some kind of fatal exception caught by main!')
    

if __name__ == '__main__':
    main()
