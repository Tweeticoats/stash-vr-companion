# stash-vr-companion
This is a companion web application to connect stash to deovr and heresphere.

Stash is a self hosted web application to manage your porn collection.
Deovr is a VR video player avalable for most platforms.

This web application creates a set of json files allowing you to stream vr videos to your oculus, vive, google carboard etc.

## Scene configuration

Stash VR Companion uses tags to configure both what is included in the index and also the scene VR format and projection.

1. All scenes *must be tagged* with `export_deovr` to be visible at all.
2. 2D scenes: the `FLAT` tag explicitly marks 2D. *Scenes are assumed 2D by default*, but explicitly tagging `FLAT` can help when searching and organizing witin Stash.
3. 3D scenes should have two tags each:
    1. *Stereo Mode*, which must be either:
        * `SBS` - Side by Side with the left eye taking up the left half of the video. This is the default for 3D videos; but setting explicitly can help you to search and filter in Stash.
        * `TB` - Top and bottom, with the left eye taking up the top half of the video.
    3. *Screen Type* (or "projection"), which must be either:
        * `DOME` - 3D 180° projection, this is what most VR videos use.
        * `FISHEYE` - Fish Eye lense projection
        * `190°` or `RF52` - 3d 190° projection used by SLR
        * `200°` or `MKX200` - 3D 200° projection used by SLR
        * `MKX220` - 3D 220° projection used by SLR
        * `SPHERE` - 3D 360° projection used by some earlier videos
        * `MONO` - Mono video with the same image for both eyes, commonly used with mono 360 videos

## Additional filter categories
The default categories are Recent, 2D and VR. You can pin a studio and performers by adding a string to the studio description and a tag to the performer.
Typically you will apply the tags "export_deovr", "FLAT" to a 2d scene or "export_deovr","DOME","SBS" for most 180° VR scenes.

To pin a studio edit the studio in stash and add the string EXPORT_DEOVR to the description field for the studio.

To Pin a performer edit the performer and add the tag export_deovr to the performer.

To Pin a tag the tag must be a sub tag of export_deovr. Edit export_deovr and add the tag as a child.

## Running in docker
Configuration is done by providing environment variables to the docker container.
The web server is running on port 5000 in the container.
The folder /cache is used for an image cache and should be configured as a docker volume.
The folder /hsp is used to store hsp files, these are configuration files used by heresphere to store scene settings including markers.

| Parameter                                     | Function                                                                                                                                                                                            |
|:----------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `-e API_URL=http://192.168.0.22:9999/graphql` | Specify the stash instance to connect to                                                                                                                                                            |
| `-e API_KEY=xxxxxxxxx`                        | Specify the api key used to connect to stash if you have password protected your instance. Note you will need to login to the web interface, deovr and heresphere with your stash username and password. |
| `-e CACHE_DIR=/cache/`                        | The directory used to cache images, defaults to /cache/ in the docker container and ./cache/ if not specified                                                                                       |
| `-e HSP_DIR=/hsp/`                            | The directory used to store hsp files saved from within heresphere, defaults to ./hsp/ if not specified                                                                                             |
| `-e DISABLE_CERT_VERIFICATION=True`           | Disable certificate verification when connecting to stash, for cases where https is used                                                                                                            |
| `-e REFRESH_MINUTES=5`                        | Refresh interval of VR scene information cache, in minutes. Defaults to 5 minutes if not specified.                                                                                                 |

```
docker stop stash-vr-companion
docker rm stash-vr-companion
docker volume create stash-vr-companion
docker volume create stash-vr-companion-hsp
docker pull ghcr.io/tweeticoats/stash-vr-companion:latest
docker run -d  --name=stash-vr-companion --restart=unless-stopped -v stash-vr-companion:/cache/ -v stash-vr-companion-hsp:/hsp/ -p 5000:5000 -e API_URL=http://192.168.0.22:9999/graphql ghcr.io/tweeticoats/stash-vr-companion:latest
```
