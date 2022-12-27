from cfg import *
from PlayonVideo import *

class PlayonWebdriver():
    def __init__(self):
        # Set up the driver so that commands can be invoked
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from chromedriver_py import binary_path as driver_path

        import logging
        self.logger = logging.getLogger('__main__')

        # Some modules (looking at you webdriver) are exceptionally noisy for debug purposes
        #  this sets them to only log if warning or higher
        for log_name, log_obj in logging.Logger.manager.loggerDict.items():
            if log_name != '__main__':
                logging.getLogger(log_name).setLevel(logging.WARNING)
        
        # Add options to allow the driver to operate in headless mode without a GUI. Required since most
        #  of the time a raspbian server isn't running a GUI anyways
        options = Options()
        options.headless = True
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.experimental_options['prefs'] = {'download.default_directory': g_paths['downloadfolder']}

        change_driver(driver_path)
        
        try:
            self.driver = webdriver.Chrome(options = options)
        except:
            logger.info("Unable to create webdriver from path, trying override from ini")
            self.driver = webdriver.Chrome(g_paths['chromewebdriver'], options = options)

    def __del__(self):
        # Explicitly close the driver, don't want a dangling head left around
        if self.driver is not None:
            self.driver.close()   

    def change_driver(self, loc):
        # https://github.com/Strip3s/PhoenixBot/blob/554441b3b6888a9be46b8aed6d364dc33da92e87/utils/selenium_utils.py#L150-L173
        import re

        fin = open(loc, 'rb')
        data = fin.read()
        val = "$" + "".join(random.choices(string.ascii_lowercase, k=3)) + "_" + \
            "".join(random.choices(string.ascii_letters + string.digits, k=22)) + "_"

        result = re.search(b"[$][a-z]{3}_[a-zA-Z0-9]{22}_", data)

        if result is not None:
            try:
                logger.debug("Changing value in Chromedriver")
                data = data.replace(result.group(0), val.encode())
                fin.close()
                fin = open(loc, 'wb')
                fin.truncate()
                fin.write(data)
                fin.close()
            except:
                logger.error("Error modifying chromedriver")
        else:
            fin.close()

    def LogInToPlayon(self):
        import time
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import NoSuchElementException
        
        self.logger.debug('Entering LogInToPlayon')
        
        playonUrl = 'https://www.playonrecorder.com/list'
        self.driver.get(playonUrl)
        
        # Long sleep to let page load
        time.sleep(10)
        email_in = self.driver.find_element(By.ID, "email")
        email_in.click()
        email_in.send_keys(g_creds['playonusername'])

        time.sleep(1)
        password_in = self.driver.find_element(By.ID, 'password')
        password_in.click()
        password_in.send_keys(g_creds['playonpassword'])

        time.sleep(1)
        
        # Max 3 attempts since Playon can be stupid and reject the login attempt, but work on retry
        attempt_count = 0
        while attempt_count < 10:
            try:
                attempt_count += 1
                login = self.driver.find_element(By.ID, 'login-button')
                login.click()
                # This longer sleep is to allow the auth to validate and load the table of hte downloads
                time.sleep(10)
            except NoSuchElementException:
                logger.debug('Exiting LogInToPlayon (Login button no longer available!)')
                return
        # There has been an issue and we were unable to actually perform the login. Maybe try to get a picture? 
        driver.save_full_page_screenshot('/Screenshots/FailedLogin.png')
        self.logger.debug('Exiting LogInToPlayon (attempt_count_timeout)')

    def CheckForNewVideos(self):
        from bs4 import BeautifulSoup
        import os
        import FilesystemHelpers as fsh
        bs = BeautifulSoup(self.driver.page_source, features='html.parser')
        tbl = bs.find(id='recording-list')
        
        if len(tbl) == 1 and tbl.findChild().text == 'You currently have no recordings to download':
            return []
        
        download_list = []
        for row in tbl:
            # Look at each recorded object. Is it already saved? if not, download
            cols = row.find_all('td')
            pv = PlayonVideo(cols)
            if not fsh.VideoIsDownloaded(pv):
                self.logger.info('Want to download: ' + pv.Title)
                download_list.append(pv)

        self.logger.debug('Required downloads queued')
        # What if someone downloads both versions of "Beauty and the beast" at the same time?
        for i in range(len(download_list)):
            duplicate_count = 0
            for j in range(i+1, len(download_list)):
                if download_list[i].Title == download_list[j].Title:
                    duplicate_count += 1
                    download_list[j].Title += " (" + str(duplicate_count) + ")"
                    
        self.logger.info('download_list: ' + PlayonArrayToStr(download_list))
        return download_list

    def SortPvByExpiration(e):
        return e.Expires

    def DownloadVideos(self, download_list):
        from selenium.webdriver.common.by import By
        from datetime import datetime
        from datetime import timedelta
        import FilesystemHelpers as fs 
        import time
        self.logger.debug('Entering DownloadVideos')
        
        # Sort so earliest expiring video is queued for download
        download_list.sort(key=SortPvByExpiration)

        min_downloads_required = 0
        # Set the stop time to 2hr before work day. This is hopefully enough time to finish queue
        stop_queue_time = datetime.today() + timedelta(days=1)
        stop_queue_time = stop_queue_time.replace(hour=int(g_settings['morningstoptime']) - 2, minute=0)
                
        finished, downloading_list = fs.GetFinishedDownloads(download_list)
        if len(finished) > 0:
            self.logger.info('Count of old downloads to be moved into plex: ' + str(len(finished)))
            fs.MoveDownloadsToPlayonFolder(finished)
            for item in finished:
                if item in download_list:
                    download_list.remove(item)
        
        for item in downloading_list:
            download_list.remove(item) # Remove from download_list since it's now tracked by inprogress
        # Force download any item expiring soon (Playon holds for about a week, so 2 days until expirey means we are behind schedule)
        for item in download_list:
            if item.Expires < datetime.today() + timedelta(days=2):
                min_downloads_required += 1

        while(True):
            # Should queue another download if:
            # 1) We have stuff expiring soon and can't delay, OR
            # 2) there is time for it to finish
            await_all = False
            if len(download_list) > 0 and ( min_downloads_required > 0 or datetime.today() < stop_queue_time):
                while len(downloading_list) < g_settings.getint('maxconcurrentdownloads', 5) and len(download_list) > 0:
                    next_video = download_list.pop(0)
                    downloadBtn = self.driver.find_element(By.ID, next_video.DownloadButtonId)
                    downloadBtn.click()
                    min_downloads_required -= 1
                    downloading_list.append(next_video)
                    # Give a few seconds for download to start
                    time.sleep(5)
            elif len(downloading_list) > 0:
                # Need to let other downloads finish. However, we have nothing left to download so we should switch to "await all"
                self.logger.debug('No downloads left to queue, just need to await remaining')
                await_all = True
            else:
                # We have no active downloads, and no required downloads / time left
                self.logger.debug('All active downloads finished, and nothing left to queue for download (or out of time)')
                break
            
            # Wait for a download to finish, then move into appropriate folder structure
            self.logger.debug('Active download count: ' + str(len(downloading_list)))
            finished = fs.WaitForDownloads(self.driver, downloading_list, await_all)
            self.logger.info('Finished downloads: ' + PlayonArrayToStr(finished))
            if len(finished) == 0 :
                self.logger.critical("WaitForDownloads returned with nothing finished in Download Videos! This should never be the case, so failing to prevent explosion of log")
                raise "DownloadVideos failed to wait"
            fs.MoveDownloadsToPlayonFolder(finished)
            for item in finished:
                if item in downloading_list:
                    downloading_list.remove(item)
            
        self.logger.debug('Exiting DownloadVideos')