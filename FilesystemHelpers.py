import logging
logger = logging.getLogger('__main__')
from cfg import *
from PlayonVideo import *

def VideoIsDownloaded(pv):   
    # Recursively search for the expected file in previously downloaded & handled
    if pv.VideoType == "Movie":
        for root, subFolders, files in os.walk(g_paths['playonroot']):
            if pv.Provider.lower() in root.lower():
                for file in files:
                    if pv.Title.lower() == os.path.splitext(file.lower())[0]:
                        logger.debug(pv.Title + ' found at ' + root)
                        return True
    elif pv.VideoType == "TvShow":
        for root, subFolders, files in os.walk(g_paths['tvroot']):
            if pv.ShowTitle.lower() in root.lower():
                for file in files:
                    if pv.Title.lower() == os.path.splitext(file.lower())[0]:
                        logger.debug(pv.Title + ' found at ' + root)
                        return True
    
    # Recursively search for the expected file in active downloads                    
    for root, subFolders, files in os.walk(g_paths['downloadfolder']):
        for file in files:
            fnameLow = os.path.splitext(file.lower())[0]
            if pv.Title.lower() == fnameLow:
                # File is downloaded (or downloading). We will add it to file mgmt list
                #  incase previous execution crashed, but no need to download a 2nd time
                logger.debug(pv.Title + ' is already being downloaded.')
                return False
    
    # We haven't been able to find the video file, therefore return false
    return False

def WaitForDownloads(driver, download_list, await_all):
    # Would be a better method than just raw sleep, but ... too much effort
    # https://newbedev.com/selenium-python-waiting-for-a-download-process-to-complete-using-chrome-web-driver
    import os, time
    
    if len(download_list) == 0:
        return []
    
    logger.debug('Entering WaitForDownloads, waiting on: ' + str([playon.Title for playon in download_list]))
    infinite_loop = True
    
    while infinite_loop:
        finished_downloads, inprogress = GetFinishedDownloads(download_list)
        if len(finished_downloads) > 0:
            if len(finished_downloads) == len(download_list):
                logger.info('All Downloads complete!')
                return finished_downloads
            if not await_all:
                logger.debug("Returning downloads that finished (since not awaiting all)")
                return finished_downloads
        if len(inprogress) == 0:
            # No downloads in progress
            logger.debug("No in progress downloads, returning")
            return []
        time.sleep(30)

def GetFinishedDownloads(download_list):
    #logger.debug('Entering GetFinishedDownloads')
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
        else:
            logger.debug('Unregistered file found by GetFinishedDownloads: ' + fnameLow)
    #logger.debug('Exiting GetFinishedDownloads')
    return finished_downloads, inprogress

def GetMovieData(name):
    import imdb
    ia = imdb.IMDb()
    possibles = ia.search_movie(name)
    for possibility in possibles:
        if possibility.data['title'].replace(':','_') == name:
            return possibility.data

def MoveMoviesToPlayonFolder(download_list):
    import os, shutil, re, time
    from datetime import date
    
    logger.debug('Entering MoveMoviesToPlayonFolder')
    
    if len(download_list) == 0:
        return
    # Correct file might look something like #_Title.mp4, but just in case it's only Title.mp4, this will still match
    playonFileRe = re.compile('\d*_?(.*)\.mp4')
    
    # Make sure a provider ('hbo max', 'disney plus') folder exists for all recorded videos
    for video in download_list:
        src_path = os.path.join(g_paths['playonroot'], video.Provider)
        if not os.path.exists(src_path):
            os.makedirs(src_path)
    
    # Iterate through download folder looking for our new videos
    for file in os.listdir(g_paths['downloadfolder']):
        results = re.match(playonFileRe, file)
        if not results:
            continue
        title = results[1]
        for video in download_list:
            if title == video.Title:
                # Create proper folder with name + year (if movie)
                logger.info('Attempting to move download (' + title + ') to appropriate folder')
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
                    logger.error('Exception generated from imdb! Defaulting to current year I guess')
                    year = str(date.today().year)
            
                folder_title = title + ' (' + year + ')'
                movie_folder = os.path.join(g_paths['downloadfolder'], folder_title)
                os.mkdir(movie_folder)
                if not movie_data:
                     logger.warning('Unable to find ' + title + ' on IMDB :( ')
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
                        attempt_count += 1
                logger.info(movie_folder + ' => ' + true_location)
                break
    logger.debug('Exiting MoveMoviesToPlayonFolder')


def MoveTvShowsToPlayonFolder(download_list):
    import os, shutil, re, time
    from datetime import date
    
    if len(download_list) == 0:
        return
    logger.debug('Entering MoveTvShowsToPlayonFolder')

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
                logger.info('Attempting to move download (' + title + ') to appropriate folder')
                final_show_path = os.path.join(g_paths['tvroot'], video.Provider, video.ShowTitle)
                final_season_path = os.path.join(final_show_path, 'Season ' + video.Season)
                
                orig_file_path = os.path.join(g_paths['downloadfolder'], file) 
                
                if not os.path.exists(final_season_path):
                    logger.debug('Something missing in path, creating: ' + final_season_path)
                    os.makedirs(final_season_path)
                
                logger.info(orig_file_path + ' => ' + final_season_path)
                shutil.move(orig_file_path, final_season_path)
                break
    logger.debug('Exiting MoveTvShowsToPlayonFolder')

def MoveDownloadsToPlayonFolder(download_list):
    movies = []
    tv_shows = []
    for video in download_list:
        if video.VideoType == "TvShow":
            tv_shows.append(video)
        elif video.VideoType == "Movie":
            movies.append(video)
        else:
            logger.error("Unknown video type: " + video.VideoType)
    
    MoveMoviesToPlayonFolder(movies)
    MoveTvShowsToPlayonFolder(tv_shows)

def GenerateDownloadList():
    # We already have downloaded files, just want to make the list in order to call everything else
    import os, re
    dlist = []
    comp = re.compile("\d*_(.*)\.mp4")
    for f in os.listdir(g_paths["downloadfolder"]):
        m = re.match(comp, f)
        if m:
            newMatch = PlayonVideo()
            newMatch.CreateRightName(m[1])

            dlist.append(newMatch)
    return dlist
