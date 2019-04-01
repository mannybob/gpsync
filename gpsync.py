from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import requests
from os import path, makedirs, stat, listdir, remove
from shutil import rmtree
from sys import exit
import argparse
from datetime import datetime, timedelta
import time
import fnmatch

SCOPES = 'https://www.googleapis.com/auth/photoslibrary.readonly'
homeDir = path.expanduser("~")
accessTokenStore = ".gp_token"
clientIdStore = ".google_clientid"
quiet = False
noUpdate = False
deleteFiles = False
deleteDirectories = False
excludePattern = None

def ParseArgs():
    parser = argparse.ArgumentParser()
    orderGroup = parser.add_mutually_exclusive_group(required=True)
    orderGroup.add_argument("-a", "--albums", help="Sync by albums", action="store_true")
    orderGroup.add_argument("-s", "--shared-albums", help="Sync by shared albums", action="store_true")
    orderGroup.add_argument("-p", "--photos", help="Sync photos", action="store_true")
    parser.add_argument("-d", "--destination-dir", help="Destination directory, default is current", type=str, default=".")
    parser.add_argument("-t", "--token-dir", help="Token directory, default is HOME", type=str)
    sizeGroup = parser.add_mutually_exclusive_group()
    sizeGroup .add_argument("-z", "--size", help="Image size <w> by <h>, default=full sized", nargs=2, metavar=('WIDTH','HEIGHT'), type=int )
    parser.add_argument("-0", "--no-update", help="List actions only", action="store_true")
    parser.add_argument("--delete-files",help="Delete local files not found on google photos", action="store_true")
    parser.add_argument("--delete-dirs",help="(With -a|-S only). Delete local directories not matching albums", action="store_true")
    parser.add_argument("-x","--exclude", help="Skip files or albums matching [EXCLUDE] (Wild cards okay.  CAUTION: excluded files/dirs will be deleted by --delete-files, --delete-dirs", type=str)
    parser.add_argument("-q","--quiet", action="store_true")
    return parser.parse_args()

def iso8601UTCdateToDate(text):
    dt = datetime.strptime( text, "%Y-%m-%dT%H:%M:%SZ")
    return dt

def getFileCreationDate(path):
    ts = stat(path).st_ctime
    dt = datetime.fromtimestamp( ts )
    return dt

# 
# Compare creation date of named file to iso8601 formatted timestamp
# on the google photos item.   Return True if google photos timestamp
# is newer or local file does not exist.
#
def UpdateRequired( gpDate, filePath ):
    if not path.exists( filePath ):
        return True

    gpDateUTC = iso8601UTCdateToDate( gpDate )
    adj = time.timezone / 3600    # hours west of GMT
    if time.localtime().tm_isdst == 1:
        adj -= 1   # Local time is DST

    gpDateLocal = gpDateUTC + timedelta(hours=adj)
    fileDate = getFileCreationDate( filePath)
    
    return gpDateLocal > fileDate

#
#  Set image download size
#
#   size = [-1,?]:   Full size
#   size = [0,?]:  No download
#   size = [W,H]:  Resize to fit WxH (maintaining original aspect ratio)
#
def SizeDescriptor( size ):
    if size[0] == -1:
        descriptor="=d"
    else:
        descriptor="=w"+str(size[0])+"-h"+str(size[1])

    return descriptor

untitledAlbumId=1

#
#  Loop through list of albums or shared albums
#
def ProcessAlbums(service, sharedAlbum, targetDir, sizeDesc):
    albumList = []

    if sharedAlbum:
        albumObj = service.sharedAlbums()
        listName = 'sharedAlbums'
    else:
        albumObj = service.albums()
        listName = 'albums'

    albumRequest = albumObj.list()
    while albumRequest is not None:
        doc = albumRequest.execute()

        if len(doc) == 0:
            # No albums
            return
 
        for item in doc[listName]:
            if ('title' in item):
                title = item['title']
                if not excludePattern is None and fnmatch.fnmatch( title, excludePattern):
                    continue
            else:
                title = 'Untitled ' + str( untitledAlbumId)
                untitledAlbumId += 1
            if not quiet:
                print('Syncing Album {0}'.format(title))
            ProcessAlbumItems( service, title, item['id'], targetDir, sizeDesc)
            
            if deleteDirectories and 'title' in item:
                albumList.append(item['title'])

        albumRequest = albumObj.list_next( albumRequest, doc)
    
    if deleteDirectories:
        DeleteDirectories( targetDir, albumList )



def DeleteDirectories( localDir, gpDirectoryList ):
    localDirList = listdir(localDir)
    for entry in localDirList:
        target = path.join(localDir, entry)
        if path.isdir( target):
            if not entry in gpDirectoryList:
                try:
                    if not noUpdate:
                        rmtree( target, ignore_errors=True ) 
                    if not quiet:
                        print("{0} deleted".format(target))
                except:
                    print("Unable to delete {0}".format(target))
        # The elif branch below always deletes all files in the 
        # root folder is the --delete-dir option is selected.
        # Probably not desired behavior
        '''                    
        elif path.isfile( target ):
            try:
                if not noUpdate:
                    remove( target ) 
                if not quiet:
                    print("{0} deleted".format(target))
            except PermissionError:
                print("Unable to delete {0}, permission denied".format(target))
            except:
                print("Unable to delete {0}".format(target))
        '''
# 
#  Delete local files not appearing in google photos
#
def DeleteFiles( localDir, gpFileList ):
    localFileList = listdir(localDir)
    for entry in localFileList:
        target = path.join(localDir, entry)
        # Skip directories
        if not path.isfile( target):
            continue

        if not entry in gpFileList:
            try:
                if not noUpdate:
                    remove( target ) 
                if not quiet:
                    print("{0} deleted".format(target))
            except PermissionError:
                print("Unable to delete {0}, permission denied".format(target))
            except:
                print("Unable to delete {0}".format(target))

#
#  Process all media items
#
def ProcessItems(service, targetDir, sizeDesc):
    gpFileList = []
    itemRequest = service.mediaItems().list()
    while itemRequest is not None:
        doc = itemRequest.execute()
        CopyItems( doc.get('mediaItems', []), targetDir, gpFileList ) 
        itemRequest = service.mediaItems().list_next( itemRequest, doc )

    if deleteFiles:
        DeleteFiles( targetDir, gpFileList)

#
#  Process all mediaItems in a given album
#
def ProcessAlbumItems(service, title, albumId, targetDir, sizeDesc):
    gpFileList = []

    # Create folder if needed
    fullPath = path.join(targetDir, title)
    if not path.exists( fullPath ) and not noUpdate:
        makedirs(fullPath)
        
    body = { "albumId": albumId}
    itemRequest = service.mediaItems().search(body=body)
    while itemRequest is not None:
        doc = itemRequest.execute()        
        CopyItems( doc.get('mediaItems', []), fullPath, gpFileList)
        itemRequest = service.mediaItems().list_next(itemRequest, doc)

    if deleteFiles and path.exists( fullPath ):
        DeleteFiles( fullPath, gpFileList)

#
#  Copy items to targetDir
#  Append list of files seen to gpFileList
#
def CopyItems(items, targetDir, gpFileList):
    for item in items:
        fileName = item['filename']
        if not excludePattern is None and fnmatch.fnmatch(fileName, excludePattern):
            continue
        filePath = path.join( targetDir, fileName)
        if UpdateRequired(item['mediaMetadata']['creationTime'], filePath):
            if not quiet:
                print('{0} -> {1}'.format(fileName, filePath))
            if not noUpdate:
                if 'video' in item['mediaMetadata']:
                    bits = GetItemBits(item['baseUrl'], sizeDesc, True )
                else:
                    bits = GetItemBits( item['baseUrl'], sizeDesc, False)
                f = open(filePath, "wb")
                f.write(bits)
                f.close()
        if deleteFiles:
            gpFileList.append( item['filename'])

#
#   Get info for mediaItem by id
#
def GetPhotoInfo(service, photoId):
    itemRequest = service.mediaItems().get(mediaItemId=photoId)
    doc = itemRequest.execute()
    return doc

#
#   Download photo using baseUrl
#
def GetItemBits(baseUrl, sizeDescriptor, isVideo):
    if isVideo:
        url = baseUrl + "=dv"
    else:
        url=baseUrl+sizeDescriptor
    r = requests.get(url)
    return r.content


#
#  OAuth2 authentication
#
def GetAccess( token_dir ):
    store = file.Storage( path.join(token_dir, accessTokenStore) )
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets( path.join(token_dir, clientIdStore), SCOPES)
        creds = tools.run_flow(flow, store)

    service = build('photoslibrary', 'v1', http=creds.authorize(Http()))
    return service

#
#  main
# 
args = ParseArgs()

quiet = args.quiet
noUpdate = args.no_update
deleteFiles = args.delete_files
deleteDirectories = args.delete_dirs
excludePattern = args.exclude

if not quiet:
    now = datetime.now().strftime("%d %B %Y %I:%M%p")
    print("gpsync starting", now)
    
if args.token_dir is None:
    args.token_dir = homeDir

service = GetAccess( args.token_dir)

if not args.size is None:
    sizeDesc = SizeDescriptor( args.size )
else:
    # default to full size
    sizeDesc = SizeDescriptor( [-1, -1])

if args.albums:
    ProcessAlbums( service, False, args.destination_dir, sizeDesc)
elif args.shared_albums:
    ProcessAlbums( service, True, args.destination_dir, sizeDesc)
else:
    ProcessItems( service, args.destination_dir, sizeDesc)
