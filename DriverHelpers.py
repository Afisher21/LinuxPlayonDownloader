import logging
logger = logging.getLogger('__main__')
from cfg import *
from PlayonVideo import *

def LogInToPlayon(driver):
    import time
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import NoSuchElementException
    
    logger.debug('Entering LogInToPlayon')
    
    playonUrl = 'https://www.playonrecorder.com/list'
    driver.get(playonUrl)
    
    # Long sleep to let page load
    time.sleep(10)
    email_in = driver.find_element(By.ID, "email")
    email_in.click()
    email_in.send_keys(g_creds['playonusername'])

    time.sleep(1)
    password_in = driver.find_element(By.ID, 'password')
    password_in.click()
    password_in.send_keys(g_creds['playonpassword'])

    time.sleep(1)
    
    # Max 3 attempts since Playon can be stupid and reject the login attempt, but work on retry
    attempt_count = 0
    while attempt_count < 3:
        try:
            login = driver.find_element(By.ID, 'login-button')
            login.click()
            # This longer sleep is to allow the auth to validate and load the table of hte downloads
            time.sleep(10)
        except NoSuchElementException:
            logger.debug('Exiting LogInToPlayon (Login button no longer available!)')
            return

    logger.debug('Exiting LogInToPlayon (attempt_count_timeout)')

def CheckForNewVideos(driver):
    from bs4 import BeautifulSoup
    import os
    import FilesystemHelpers as fsh
    bs = BeautifulSoup(driver.page_source, features='html.parser')
    tbl = bs.find(id='recording-list')
    
    if len(tbl) == 1 and tbl.findChild().text == 'You currently have no recordings to download':
        return []
    
    download_list = []
    for row in tbl:
        # Look at each recorded object. Is it already saved? if not, download
        cols = row.find_all('td')
        pv = PlayonVideo(cols)
        if not fsh.VideoIsDownloaded(pv):
            logger.info('Want to download: ' + pv.Title)
            download_list.append(pv)

    logger.debug('Required downloads queued')
    # What if someone downloads both versions of "Beauty and the beast" at the same time?
    for i in range(len(download_list)):
        duplicate_count = 0
        for j in range(i+1, len(download_list)):
            if download_list[i].Title == download_list[j].Title:
                duplicate_count += 1
                download_list[j].Title += " (" + str(duplicate_count) + ")"
                
    logger.info('download_list: ' + PlayonArrayToStr(download_list))
    return download_list

def SortPvByExpiration(e):
    return e.Expires

def DownloadVideos(driver, download_list):
    from selenium.webdriver.common.by import By
    from datetime import datetime
    from datetime import timedelta
    import FilesystemHelpers as fs 
    import time
    logger.debug('Entering DownloadVideos')
    
    # Sort so earliest expiring video is queued for download
    download_list.sort(key=SortPvByExpiration)

    min_downloads_required = 0
    # Set the stop time to 2hr before work day. This is hopefully enough time to finish queue
    stop_queue_time = datetime.today() + timedelta(days=1)
    stop_queue_time = stop_queue_time.replace(hour=int(g_settings['morningstoptime']) - 2, minute=0)
            
    finished, downloading_list = fs.GetFinishedDownloads(download_list)
    if len(finished) > 0:
        logger.info('Count of old downloads to be moved into plex: ' + str(len(finished)))
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
                downloadBtn = driver.find_element(By.ID, next_video.DownloadButtonId)
                downloadBtn.click()
                min_downloads_required -= 1
                downloading_list.append(next_video)
                # Give a few seconds for download to start
                time.sleep(5)
        elif len(downloading_list) > 0:
            # Need to let other downloads finish. However, we have nothing left to download so we should switch to "await all"
            logger.debug('No downloads left to queue, just need to await remaining')
            await_all = True
        else:
            # We have no active downloads, and no required downloads / time left
            logger.debug('All active downloads finished, and nothing left to queue for download (or out of time)')
            break
        
        # Wait for a download to finish, then move into appropriate folder structure
        logger.debug('Active download count: ' + str(len(downloading_list)))
        finished = fs.WaitForDownloads(driver, downloading_list, await_all)
        logger.info('Finished downloads: ' + PlayonArrayToStr(finished))
        if len(finished) == 0 :
            logger.critical("WaitForDownloads returned with nothing finished in Download Videos! This should never be the case, so failing to prevent explosion of log")
            raise "DownloadVideos failed to wait"
        fs.MoveDownloadsToPlayonFolder(finished)
        for item in finished:
            if item in downloading_list:
                downloading_list.remove(item)
        
    logger.debug('Exiting DownloadVideos')