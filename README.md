# gpsync

Gpsync is a python utility to download and update google photos on the local machine.   Despite it's name this is a one-way sync only.

Also, I hope it serves as an example to use the google photos API in python, as the official documentation is suboptimal, and google has not provided an official python sample.

Before running for the first time, follow the guide https://developers.google.com/photos/library/guides/get-started to create a client token and authorize it to access google photos.  Google ask for a project name, and an application name.  Choose any name you like.  The name needn't be unique or even meaningful.

You will also need to install the google API client library for python.  Installation instruction are here: https://developers.google.com/api-client-library/python/start/installation

Once you have credentials, download the credentials file and save it as *.google_client_id* in your token directory. (Default is $HOME in Linux, %HOMEPATH% in windows, override with *-t*).

The first time you run the app, google will open a browser window to ask for permission to access your photos.   After that, the app will use the stored access token in *.gp_token* in your token directory.

### Usage:

    python gpsync.py [-h] (-a | -s | -p) [-d DESTINATION_DIR] [-t TOKEN_DIR]
                 [-z WIDTH HEIGHT] [-0] [--delete-files] [--delete-dirs]
                 [-x EXCLUDE] [-q]
                 
### Arguments:
    One (and only one) of -a, -s, -p is required:
    -a, --albums          Sync by albums
    -s, --shared-albums   Sync by shared albums
    -p, --photos          Sync photos
    
    -d DESTINATION_DIR, --destination-dir DESTINATION_DIR
                          Destination directory, default is current
    -t TOKEN_DIR, --token-dir TOKEN_DIR
                          Token directory, default is HOME
    -z WIDTH HEIGHT, --size WIDTH HEIGHT
                          Image size <w> by <h>, default=full sized
    -0, --no-copy         No copy, list actions only
    --delete-files        Delete local files not found on google photos
    --delete-dirs         (With -a|-S only). Delete local directories not
                          matching albums
    -x EXCLUDE, --exclude EXCLUDE
                          Skip files or albums matching [EXCLUDE] (Wild cards
                          okay. CAUTION: excluded files/dirs will be deleted by
                          --delete-files, --delete-dirs                          
    -q, --quiet
    -h, --help            show this help message and exit
    
### Quirks features and issues:
* When syncing by albums (or shared albums) gpsync creates a directory for each album.
* The resize option (-z) is ignored for videos. (The API does support resize, but it generates a thumbnail image only).
* Googles idea of your shared albums, photos, may not match your expectations.  Try python gpsync.py -0.
* Google photo does not support modification time (as of API v1), so gpsync downloads item updates based on file create date.
* Unnamed albums are saved as *Untitled <#>* where #=1,2,etc.

