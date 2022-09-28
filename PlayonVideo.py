class PlayonVideo:
    def __init__(self, tr=None):
        if tr is None:
            self.Provider = "Default"
            return
        
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
            self.ShowTitle = self.ShowTitle.rstrip('-').strip() # Remove trailing '-' if present
            self.Season = episode_parts[2][1:]
            self.Episode = episode_parts[3][1:]
            self.EpisodeTitle = episode_parts[4].replace(':',' ').replace('-', ' ').strip()
            self.VideoType = "TvShow"
            self.Title = self.ShowTitle + ' - ' + episode_parts[2] + episode_parts[3] + ' - ' +  self.EpisodeTitle
        else:
            self.Title = title.replace(':', '_').replace('/','_')
            self.VideoType = "Movie"
