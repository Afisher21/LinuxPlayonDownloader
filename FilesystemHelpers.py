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
                        attempt_count += 1
                logging.info(movie_folder + ' => ' + true_location)
                break

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
                break

def GenerateDownloadList():
    # We already have downlaoded files, just want to make the list in order to call everything else
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
