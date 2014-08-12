#!/usr/bin/python

import httplib2, os, pickle, sys, shlex, subprocess, time

from mutagen.easyid3 import EasyID3
from os import listdir
from os.path import isfile, join
from apiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

class YouTube:
    @staticmethod
    def gimme():
        CLIENT_SECRETS_FILE = "client_secrets.json"
        
        MISSING_CLIENT_SECRETS_MESSAGE = """
        WARNING: Please configure OAuth 2.0
        
        To make this sample run you will need to populate the client_secrets.json file
        found at:
        
           %s
        
        with information from the Developers Console
        https://console.developers.google.com/
        
        For more information about the client_secrets.json file format, please visit:
        https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
        """ % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                           CLIENT_SECRETS_FILE))
        
        YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
        YOUTUBE_API_SERVICE_NAME = "youtube"
        YOUTUBE_API_VERSION = "v3"
        
        flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
          message=MISSING_CLIENT_SECRETS_MESSAGE,
          scope=YOUTUBE_READONLY_SCOPE)
        
        storage = Storage("%s-oauth2.json" % sys.argv[0])
        credentials = storage.get()
        
        if credentials is None or credentials.invalid:
            flags = argparser.parse_args()
            credentials = run_flow(flow, storage, flags)
        
        return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
          http=credentials.authorize(httplib2.Http()))

def logData(info):
    f = open("YouSync.log", "a")
    f.write(time.strftime("%c") + " " + info + "\n")
    f.close()
    
def writeDb(db, fname):
    f = open(fname, 'w')
    x = pickle.dumps(db)
    f.write(x)
    f.close()
    
def findDb(fileId):
    fname = fileId + ".db"
    
    if not os.path.isfile(fname):
        db = dict()
        writeDb(db, fname)
        
    f = open(fname, 'r+')
    
    db = pickle.loads(f.read())
    
    f.close()
    
    return db
        
if __name__ == "__main__":
    youtube = YouTube.gimme()
    
    if len(sys.argv) > 1:
        baseDir = sys.argv[1]
    else:
        baseDir = "~"
    
    if not baseDir.endswith('/'):
        baseDir += '/'
    
    fname = "playlists.txt"
    
    if not os.path.isfile(fname):
        print "Please supply playlist IDs in playlists.txt"
        sys.exit(0)
        
    with open(fname) as f:
        for line in f:
            if line.startswith('#'):
                continue
            
            line = line.strip()
            
            db = findDb(line)
            
            title_response = youtube.playlists().list(
              id=line,
              part="snippet").execute()
            
            playlist_title = "default"
            
            for title_item in title_response["items"]:
                playlist_title = title_item["snippet"]["title"]
            
            playlistitems_list_request = youtube.playlistItems().list(
              playlistId=line,
              part="snippet",
              maxResults=50
            )
        
            while playlistitems_list_request:
                playlistitems_list_response = playlistitems_list_request.execute()
        
                for playlist_item in playlistitems_list_response["items"]:
                    title = playlist_item["snippet"]["title"]
                    video_id = playlist_item["snippet"]["resourceId"]["videoId"]
            
                    if video_id not in db:
                        
                        fullDir = baseDir + playlist_title
                        
                        if not os.path.exists(fullDir):
                            os.makedirs(fullDir)
                        
                        #This is annoying, since we can't predict the name of the newly downloaded mp3
                        files_before = [f for f in listdir(fullDir) if isfile(join(fullDir,f))]
                        
                        print "Downloading " + title
                        args = shlex.split("/usr/local/bin/youtube-dl -q -o \"" + fullDir + "/%(title)s.%(ext)s\" -f bestaudio -x --audio-format mp3 --audio-quality 192K http://www.youtube.com/watch?v=" + video_id)
                        p = subprocess.Popen(args)
                        if not p.wait() == 0:
                            logData("Problem downloading " + title.encode('ascii', 'ignore'))
                        else:
                            logData("OK downloading " + title.encode('ascii', 'ignore'))
                            db[video_id] = 1
                            
                            files_after = [f for f in listdir(fullDir) if isfile(join(fullDir,f))]
                            
                            new_file = list(set(files_after) - set(files_before))
                            
                            #Otherwise sadtimes
                            assert len(new_file) == 1
                            
                            audio = EasyID3(fullDir + "/" + new_file[0])
                            audio["title"] = title;
                            audio["album"] = playlist_title
                            audio["tracknumber"] = str(len(files_after))
                            audio.save()

                    writeDb(db, line + ".db")
                        
                playlistitems_list_request = youtube.playlistItems().list_next(playlistitems_list_request, playlistitems_list_response)
                
