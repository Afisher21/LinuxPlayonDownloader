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

class PlayonVideo:
    def __init__(self, tr):
        self.DownloadButtonId = tr[0].i['id']
         # When downloading, this will happen automatically thanks to chrome. This just lets us find the right file. Further, IMDB doesn't care about ':' vs '_', so just make everything match
        self.CreateRightName(tr[1].text)
        self.Provider = tr[2].text
        self.Size = tr[3].text
        self.Duration = tr[4].text
        # These are datefields and should be modified into such
        self.Created = self.ConvertFromPvTime(tr[5].text)
        self.Expires = self.ConvertFromPvTime(tr[6].text)
        
    def ConvertFromPvTime(self, tm):
        from datetime import datetime
        # tm is expected to be "Jan 17, 2022"
        return datetime.strptime(tm, '%b %d, %Y')
    
    def CreateRightName(self, title):
        import re
        tv_filter = re.compile(r"(.*)([Ss]\d{2})([Ee]\d{2})(.*)")
        episode_parts = re.match(tv_filter, title)
        if episode_parts:
            self.ShowTitle = episode_parts[1].replace(':',' ').replace('_', ' ').strip()
            self.Season = episode_parts[2][1:]
            self.Episode = episode_parts[3][1:]
            self.EpisodeTitle = episode_parts[4].replace(':',' ').replace('-', ' ').strip()
            self.VideoType = "TvShow"
            self.Title = self.ShowTitle + ' - ' + episode_parts[2] + episode_parts[3] + ' - ' +  self.EpisodeTitle
        else:
            self.Title = title.replace(':', '_').replace('/','_')
            self.VideoType = "Movie"
        


def LogInToPlayon(driver):
    import time
    from selenium.webdriver.common.by import By
    
    logging.debug('Entering LogInToPlayon')
    
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
    login = driver.find_element(By.ID, 'login-button')
    login.click()
    time.sleep(10)
    # Long sleep to let 'Your recordings' page load
    logging.debug('Exiting LogInToPlayon (and presuming success)')

def CheckForNewVideos(driver):
    from bs4 import BeautifulSoup
    import os
    bs = BeautifulSoup(driver.page_source, features='html.parser')
    tbl = bs.find(id='recording-list')
    
    if len(tbl) == 1 and tbl.findChild().text == 'You currently have no recordings to download':
        return []
    
    download_list = []
    for row in tbl:
        # Look at each recorded object. Is it already saved? if not, download
        cols = row.find_all('td')
        pv = PlayonVideo(cols)
        needToDownload = True
        
        # Recursively search for the expected file in previously downloaded & handled
        if pv.VideoType == "Movie":
            for root, subFolders, files in os.walk(g_paths['playonroot']):
                if pv.Provider.lower() in root.lower():
                    for file in files:
                        if pv.Title.lower() == os.path.splitext(file.lower())[0]:
                            logging.debug(pv.Title + ' should already be available in plex.')
                            needToDownload = False
                            break
        elif pv.VideoType == "TvShow":
            for root, subFolders, files in os.walk(g_paths['tvroot']):
                if pv.ShowTitle.lower() in root.lower():
                    for file in files:
                        if pv.Title.lower() == os.path.splitext(file.lower())[0]:
                            logging.debug(pv.Title + ' should already be available in plex.')
                            needToDownload = False
                            break
        
        # Recursively search for the expected file in active downloads                    
        for root, subFolders, files in os.walk(g_paths['downloadfolder']):
            for file in files:
                fnameLow = os.path.splitext(file.lower())[0]
                if pv.Title.lower() == fnameLow:
                    # File is downloaded (or downloading). We will add it to file mgmt list
                    #  incase previous execution crashed, but no need to download a 2nd time
                    logging.debug(pv.Title + ' is already being downloaded.')
                    needToDownload = False
                    download_list.append(pv)
                    break

        if needToDownload:
            logging.info('Want to download: ' + pv.Title)
            download_list.append(pv)

    logging.debug('Required downloads queued')
    # What if someone downloads both versions of "Beauty and the beast" at the same time?
    for i in range(len(download_list)):
        duplicate_count = 0
        for j in range(i+1, len(download_list)):
            if download_list[i].Title == download_list[j].Title:
                duplicate_count += 1
                download_list[j].Title += " (" + str(duplicate_count) + ")"
                
    
    return download_list

def SortPvByExpiration(e):
    return e.Expires

def DownloadVideos(driver, download_list):
    from selenium.webdriver.common.by import By
    from datetime import datetime
    from datetime import timedelta
    import time
    logging.debug('Entering DownloadVideos')
    
    # Sort so earliest expiring video is queued for download
    download_list.sort(key=SortPvByExpiration)

    min_downloads_required = 0
    # Set the stop time to 2hr before work day. This is hopefully enough time to finish queue
    stop_queue_time = datetime.today() + timedelta(days=1)
    stop_queue_time = stop_queue_time.replace(hour=int(g_settings['morningstoptime']) - 2, minute=0)
            
    finished, downloading_list = GetFinishedDownloads(download_list)
    if len(finished) > 0:
        logging.info('Count of old downloads to be moved into plex: ' + str(len(finished)))
        MoveDownloadsToPlayonFolder(finished)
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
            logging.debug('No downloads left to queue, just need to await remaining')
            await_all = True
        else:
            # We have no active downloads, and no required downloads / time left
            logging.debug('All active downloads finished, and nothing left to queue for download (or out of time)')
            break
        
        # Wait for a download to finish, then move into appropriate folder structure
        logging.debug('Active download count: ' + str(len(downloading_list)))
        finished = WaitForDownloads(driver, downloading_list, await_all)
        logging.info('Finished ' + str(len(finished)) + ' downloads')
        if len(finished) == 0 :
            logging.critical("WaitForDownloads returned with nothing finished in Download Videos! This should never be the case, so failing to prevent explosion of log")
            raise "DownloadVideos failed to wait"
        MoveDownloadsToPlayonFolder(finished)
        for item in finished:
            if item in downloading_list:
                downloading_list.remove(item)
        
    logging.debug('Exiting DownloadVideos')

def GetFinishedDownloads(download_list):
    finished_downloads = []
    inprogress = []
    video_map = {}
    for video in download_list:
        video_map[video.Title.lower()] = video
    
    # Iterate through downloaded files
    for filename in os.listdir(g_paths['downloadfolder']):
        fnameLow, extension = os.path.splitext(filename.lower())
        inProgName = os.path.splitext(fnameLow)[0]
        # fnameLow might be 'hunger games.mp4' if the original file was 'hunger games.mp4.crdownload'
        if fnameLow in video_map.keys() or inProgName in video_map.keys():
            if extension != '.crdownload':
                finished_downloads.append(video_map[fnameLow])
            else:
                inprogress.append(video_map[inProgName])
    return finished_downloads, inprogress

def WaitForDownloads(driver, download_list, await_all):
    # Would be a better method than just raw sleep, but ... too much effort
    # https://newbedev.com/selenium-python-waiting-for-a-download-process-to-complete-using-chrome-web-driver
    import os, time
    
    if len(download_list) == 0:
        return []
    
    logging.debug('Entering WaitForDownloads, waiting on: ' + str([playon.Title for playon in download_list]))
    infinite_loop = True
    
    while infinite_loop:
        finished_downloads, inprogress = GetFinishedDownloads(download_list)
        if len(finished_downloads) > 0:
            if len(finished_downloads) == len(download_list):
                logging.info('All Downloads complete!')
                return finished_downloads
            if not await_all:
                logging.debug("Returning downloads that finished (since not awaiting all)")
                return finished_downloads
        if len(inprogress) == 0:
            # No downloads in progress
            logging.debug("No in progress downloads, returning")
            return []
        time.sleep(30)

def GetMovieData(name):
    import imdb
    ia = imdb.IMDb()
    possibles = ia.search_movie(name)
    for possibility in possibles:
        if possibility.data['title'].replace(':','_') == name:
            return possibility.data

def MoveDownloadsToPlayonFolder(download_list):
    movies = []
    tv_shows = []
    for video in download_list:
        if video.VideoType == "TvShow":
            tv_shows.append(video)
        elif video.VideoType == "Movie":
            movies.append(video)
        else:
            logging.error("Unknown video type: " + video.VideoType)
    
    MoveMoviesToPlayonFolder(movies)
    MoveTvShowsToPlayonFolder(tv_shows)

def MoveMoviesToPlayonFolder(download_list):
    import os, shutil, re, time
    from datetime import date
    
    if len(download_list) == 0:
        return
    # Correct file might look something like #_Title.mp4, but just in case it's only Title.mp4, this will still match
    playonFileRe = re.compile('\d*_?(.*)\.mp4')
    
    # Make sure a provider ('hbo max', 'disney plus') folder exists for all recorded videos
    for video in download_list:
        src_path = os.path.join(g_paths['playonroot'], video.Provider)
        if not exists(src_path):
            os.mkdir(src_path)
    
    # Iterate through download folder looking for our new videos
    for file in os.listdir(g_paths['downloadfolder']):
        results = re.match(playonFileRe, file)
        if not results:
            continue
        title = results[1]
        for video in download_list:
            if title == video.Title:
                # Create proper folder with name + year (if movie)
                logging.info('Attempting to move download (' + title + ') to appropriate folder')
                year = ''
                movie_date = []
                try:
                    movie_data = GetMovieData(title)
                    if movie_data:
                        year = str(movie_data['year'])
                    else:
                        # Video is so new (or so under reported) it doesn't have a year yet. We'll try the 
                        #  current year, but can always come back later and fix if it isn't appearing correctly
                        year = str(date.today().year)
                except:
                    logging.error('Exception generated from imdb! Defaulting to current year I guess')
                    year = str(date.today().year)
            
                folder_title = title + ' (' + year + ')'
                movie_folder = os.path.join(g_paths['downloadfolder'], folder_title)
                os.mkdir(movie_folder)
                if not movie_data:
                     logging.warning('Unable to find ' + title + ' on IMDB :( ')
                     f = open(os.path.join(movie_folder, 'Guesswork.txt'), mode='x')
                     f.write("Couldn't find the file in IMDB. Chose to assume it is " + year + ", but if not the case, please correct!")
                     f.close()

                # Move the downloaded file into it's corresponding movie folder
                shutil.move(os.path.join(g_paths['downloadfolder'], file), movie_folder)

                # Move the movie folder to the playon subdirectory for that provider
                final_location = os.path.join(g_paths['playonroot'], video.Provider, folder_title)
                # What if someone records "Beauty and the Beast" and then also recorded the live-action version?
                attempt_count = 0
                failed = True
                true_location = ""
                while failed:
                    try:
                        true_location = final_location if attempt_count == 0 else final_location + "_" + str(attempt_count)
                        shutil.move(movie_folder, true_location)
                        failed = False
                    except:
                        attempt_count += 1;
                logging.info(movie_folder + ' => ' + true_location)

def MoveTvShowsToPlayonFolder(download_list):
    import os, shutil, re, time
    from datetime import date
    
    if len(download_list) == 0:
        return
    # Correct file might look something like #_Title.mp4, but just in case it's only Title.mp4, this will still match
    playonFileRe = re.compile('\d*_?(.*)\.mp4')
    # Components specific to tv episodes:
    #   video.ShowTitle
    #   video.Season
    #   video.Episode
    #   video.EpisodeTitle
    
    # Iterate through download folder looking for our new videos
    for file in os.listdir(g_paths['downloadfolder']):
        results = re.match(playonFileRe, file)
        if not results:
            continue
        title = results[1]
        for video in download_list:
            if title == video.Title:
                # Create proper folder 
                logging.info('Attempting to move download (' + title + ') to appropriate folder')
                final_show_path = os.path.join(g_paths['tvroot'], video.Provider, video.ShowTitle)
                final_season_path = os.path.join(final_show_path, 'Season ' + video.Season)
                
                orig_file_path = os.path.join(g_paths['downloadfolder'], file) 
                
                if not os.path.exists(final_season_path):
                    logging.debug('Something missing in path, creating: ' + final_season_path)
                    os.makedirs(final_season_path)
                
                logging.info(orig_file_path + ' => ' + final_season_path)
                shutil.move(orig_file_path, final_season_path)

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
    main()