# stash-vr-companion
This is a companion web application to connect stash to deovr.

Stash is a self hosted web application to manage your porn collection.
Deovr is a VR video player avalable for most platforms.

This web application creates a set of json files allowing you to stream vr videos to your oculus, vive, google carboard etc.


## Scene configuration
This web application uses tags to configure what is included in the index.
Scenes must be tagged with export_deovr to be visible.
Scenes are assumed 2d by default and to explicitly mark a scene as 2d apply the tag FLAT.
Most VR scenes are 180° with the left and right eye side by side, apply the tags export_deovr, DOME and optionally SBS to mark the video as VR.
* **export_deovr** - apply this tag to include it in the index
* **FLAT** - Mark the video as 2d. This is the default if other projection tags are not configured.
* **DOME** - 3D 180° projection, this is what most VR video's use.
* **SPHERE** - 3D 360° projection used by some earlier videos
* **FISHEYE** - Fish Eye lense projection
* **MKX200** - 3D 200° projection used by SLR
* **SBS** - Side by Side with the left eye taking up the left half of the video. This is the default for 3d video's.
* **TB** - Up Down with the left eye taking up the top half of the video.

## Additional filter categories
The default categories are Recent, 2D and VR. You can pin a studio and performers by adding a string to the studio description and a tag to the performer.

To pin a studio edit the studio in stash and add the string EXPORT_DEOVR to the description field for the studio.

To Pin a performer edit the performer and add the tag export_deovr to the performer.

To Pin a tag the tag must be a sub tag of export_deovr. Edit export_deovr and add the tag as a child.

## Running in docker
Configuration is done by providing environment variables to the docker container.
The web server is running on port 5000 in the container.
The folder /cache is used for an image cache, this can be stored in 

| Parameter                                     | Function                                                                                                      |
|:----------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| `-e API_URL=http://192.168.0.22:9999/graphql` | Specify the stash instance to connect to                                                                      |
| `-e API_KEY=xxxxxxxxx`                        | Specify the api key used to connect to stash if you have password protected your instance                     |
| `-e CACHE_DIR=/cache/`                        | The directory used to cache images, defaults to /cache/ in the docker container and ./cache/ if not specified |
| `-e DISABLE_CERT_VERIFICATION=True`           | Disable certificate verification when connecting to stash, for cases where https is used                      |
| `-e DEOVR_USERNAME=user`                      | Username to require for authentication to the deovr endpoint                                                  |
| `-e DEOVR_PASSWORD=xxxx`                      | Password to require for authentication to the deovr endpoint                                                  |

```
docker stop stash-vr-companion
docker rm stash-vr-companion
docker volume create stash-cr-companion
docker pull ghcr.io/tweeticoats/stash-vr-companion:latest
docker run -d  --name=stash-vr-companion --restart=unless-stopped -v stash-cr-companion:/cache/ -p 5000:5000 -e API_URL=http://192.168.0.22:9999/graphql ghcr.io/tweeticoats/stash-vr-companion:latest
```