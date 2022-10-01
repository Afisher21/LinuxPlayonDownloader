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
            # She-Hulk: Attorney at Law: s01e04 - Is this not real magic? ==>
            # She-Hulk_ Attorney at Law - s01e04 - Is this not real magic?
            self.ShowTitle = episode_parts[1].strip()
            if self.ShowTitle.endswith(':') or self.ShowTitle.endswith('-'):
                # The colon/hyphen after show title should be ignored
                self.ShowTitle = self.ShowTitle[:-1].strip()
            self.ShowTitle.replace(':','_') # Chromium/playon doesn't like colons, and replaces with underscore
            self.Season = episode_parts[2][1:]
            self.Episode = episode_parts[3][1:]
            self.EpisodeTitle = episode_parts[4].replace(':',' ').replace('-', ' ').strip()
            self.VideoType = "TvShow"
            self.Title = self.ShowTitle + ' - ' + episode_parts[2] + episode_parts[3] + ' - ' +  self.EpisodeTitle
        else:
            self.Title = title.replace(':', '_').replace('/','_')
            self.VideoType = "Movie"

def PlayonArrayToStr(pv_arr):
    if len(pv_arr) == 0:
        return '[]'
    out_str = '['
    for pv in pv_arr:
        out_str += pv.Title + ','
    out_str = out_str[:-1] + ']'
    return out_str