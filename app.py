from flask import Flask,jsonify,render_template,request,Response,redirect
import requests
import json
import os


app = Flask(__name__)

#app.config['SERVER_NAME'] = 'http://deovr.home'
app.config['GRAPHQL_API'] = os.getenv('API_URL', 'http://localhost:9999/graphql')



headers = {
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Connection": "keep-alive",
    "DNT": "1"
}
if os.getenv('API_KEY'):
    headers['ApiKey']=os.getenv('API_KEY')

studios=[]
performers=[]


def __callGraphQL(query, variables=None):
    json = {}
    json['query'] = query
    if variables != None:
        json['variables'] = variables

    # handle cookies
    response = requests.post(app.config['GRAPHQL_API'], json=json, headers=headers)

    if response.status_code == 200:
        result = response.json()
        if result.get("error", None):
            for error in result["error"]["errors"]:
                raise Exception("GraphQL error: {}".format(error))
        if result.get("data", None):
            return result.get("data")
    else:
        raise Exception(
            "GraphQL query failed:{} - {}. Query: {}. Variables: {}".format(response.status_code, response.content,
                                                                            query, variables))

def get_scenes_with_tag( tag):
    tagID = findTagIdWithName(tag)
    return get_scenes({"tags": {"value": [tagID], "modifier": "INCLUDES_ALL"}})

def get_scenes(scene_filter):
    query = """query findScenes($scene_filter: SceneFilterType!) {
findScenes(scene_filter: $scene_filter filter: {sort: "date",direction: DESC,per_page: -1} ) {
count
scenes {
  id
  checksum
  oshash
  title
  details
  url
  date
  rating
  organized
  o_counter
  path
  file {
    size
    duration
    video_codec
    audio_codec
    width
    height
    framerate
    bitrate
  }
  paths {
    screenshot
    preview
    stream
    webp
    vtt
    chapters_vtt
    sprite
    funscript
  }
  galleries {
    id
    checksum
    path
    title
    url
    date
    details
    rating
    organized
    studio {
      id
      name
      url
    }
    image_count
    tags {
      id
      name
      image_path
      scene_count
    }
  }
  performers {
    id
    name
    gender
    url
    twitter
    instagram
    birthdate
    ethnicity
    country
    eye_color
    country
    height
    measurements
    fake_tits
    career_length
    tattoos
    piercings
    aliases
  }
  studio{
    id
    name
    url
    stash_ids{
      endpoint
      stash_id
    }
  }
tags{
    id
    name
  }

  stash_ids{
    endpoint
    stash_id
  }
}
}
}"""

    variables = {"scene_filter": scene_filter}
    result = __callGraphQL(query, variables)
    return result["findScenes"]["scenes"]


def lookupScene(id):
    query = """query findScene($scene_id: ID!){
findScene(id: $scene_id){
  id
  checksum
  oshash
  title
  details
  url
  date
  rating
  organized
  o_counter
  path
  file {
    size
    duration
    video_codec
    audio_codec
    width
    height
    framerate
    bitrate
  }
  paths {
    screenshot
    preview
    stream
    webp
    vtt
    chapters_vtt
    sprite
    funscript
  }
  galleries {
    id
    checksum
    path
    title
    url
    date
    details
    rating
    organized
    studio {
      id
      name
      url
    }
    image_count
    tags {
      id
      name
      image_path
      scene_count
    }
  }
  performers {
    id
    name
    gender
    url
    twitter
    instagram
    birthdate
    ethnicity
    country
    eye_color
    country
    height
    measurements
    fake_tits
    career_length
    tattoos
    piercings
    aliases
  }
  studio{
    id
    name
    url
    stash_ids{
      endpoint
      stash_id
    }
  }
tags{
    id
    name
  }

  stash_ids{
    endpoint
    stash_id
  }
}
}"""
    variables = {"scene_id": id}
    result = __callGraphQL(query, variables)
    return result["findScene"]

def findTagIdWithName(name):
    query = """query {
allTags {
id
name
}
}"""

    result = __callGraphQL(query)

    for tag in result["allTags"]:
        if tag["name"] == name:
            return tag["id"]
    return None

def findPerformerIdWithName(name):
    query = """query {
  allPerformers {
    id
    name
  }
}"""
    result = __callGraphQL(query)
    for tag in result["allPerformers"]:
        if tag["name"] == name:
            return tag["id"]
    return None

def findStudioIdWithName(name):
    query = """query {
  allStudios {
    id
    name
  }
}"""
    result = __callGraphQL(query)
    for tag in result["allStudios"]:
        if tag["name"] == name:
            return tag["id"]
    return None


@app.route('/deovr')
def deovr():
#    scenes = get_scenes_with_tag("export_deovr")
    data = {}
    index = 1

    data["scenes"] = []
    for filter_id in filter():
        res=[]
        scenes_filter = {}
        if filter_id == 'Recent':
            tags = [findTagIdWithName('export_deovr')]
            scenes_filter = {"tags": {"value": tags, "depth": 0, "modifier": "INCLUDES_ALL"}}
        elif filter_id == '2D':
            tags = [findTagIdWithName('export_deovr'), findTagIdWithName('FLAT')]
            scenes_filter = {"tags": {"value": tags, "depth": 0, "modifier": "INCLUDES_ALL"}}
        elif filter_id == 'VR':
            tags = [findTagIdWithName('export_deovr'), findTagIdWithName('SBS')]
            scenes_filter = {"tags": {"value": tags, "depth": 0, "modifier": "INCLUDES_ALL"}}
        elif filter_id in studios:
            studio_ids = [findStudioIdWithName(filter_id)]
            scenes_filter = {
                "tags": {"depth": 0, "modifier": "INCLUDES_ALL", "value": [findTagIdWithName('export_deovr')]},
                "studios": {"depth": 3, "modifier": "INCLUDES_ALL", "value": studio_ids}}
        elif filter_id in performers:
            performer_ids = [findPerformerIdWithName(filter_id)]
            scenes_filter = {
                "tags": {"depth": 0, "modifier": "INCLUDES_ALL", "value": [findTagIdWithName('export_deovr')]},
                "performers": {"modifier": "INCLUDES_ALL", "value": performer_ids}}
        scenes = get_scenes(scenes_filter)
        for s in scenes:
            r={}
            r["title"] = s["title"]
            r["videoLength"]=int(s["file"]["duration"])
            if 'ApiKey' in headers:
                screenshot_url = s["paths"]["screenshot"]
                r["thumbnailUrl"] = request.base_url[:-6] + '/image_proxy?scene_id=' + screenshot_url.split('/')[4] + '&session_id=' + screenshot_url.split('/')[5][11:]
            else:
                r["thumbnailUrl"] =s["paths"]["screenshot"]
            r["video_url"]=request.base_url+'/'+s["id"]
            res.append(r)

        data["scenes"].append({"name":filter_id,"list":res})
    return jsonify(data)


@app.route('/deovr/<int:scene_id>')
def show_post(scene_id):
    s = lookupScene(scene_id)

    scene = {}
    scene["id"] = s["id"]
    scene["title"] = s["title"]
    scene["authorized"] = 1
    scene["description"] = s["details"]
#    if "studio" in s and s["studio"] is not None:
#        scene["paysite"] = {"id": 1, "name": s["studio"]["name"], "is3rdParty": True}
#        if s["studio"]["name"] in studio_cache:
#            studio_cache[s["studio"]["name"]].append(r)
#        else:
#            studio_cache[s["studio"]["name"]] = [r]
    if 'ApiKey' in headers:
        screenshot_url = s["paths"]["screenshot"]
        scene["thumbnailUrl"] = request.base_url[:-6] + '/image_proxy?scene_id=' + screenshot_url.split('/')[4] + '&session_id=' + screenshot_url.split('/')[5][11:]
    else:
        scene["thumbnailUrl"] = s["paths"]["screenshot"]
    scene["isFavorite"] = False
    scene["isScripted"] = False
    scene["isWatchlist"] = False

    vs = {}
    vs["resolution"] = s["file"]["height"]
    vs["height"] = s["file"]["height"]
    vs["width"] = s["file"]["width"]
    vs["size"] = s["file"]["size"]
    vs["url"] = s["paths"]["stream"]
    scene["encodings"] = [{"name": s["file"]["video_codec"], "videoSources": [vs]}]

    if "180_180x180_3dh_LR" in s["path"]:
        scene["is3d"] = True
        scene["screenType"] = "dome"
        scene["stereoMode"] = "sbs"
    else:
        scene["screenType"] = "flat"
        scene["is3d"] = False
    if 'SBS' in [x["name"] for x in s["tags"]]:
        scene["stereoMode"] = "sbs"
    elif 'TB' in [x["name"] for x in s["tags"]]:
        scene["stereoMode"] = "tb"

    if 'FLAT' in [x["name"] for x in s["tags"]]:
        scene["screenType"] = "flat"
        scene["is3d"] = False
    elif 'DOME' in [x["name"] for x in s["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "dome"
    elif 'SPHERE' in [x["name"] for x in s["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "sphere"
    elif 'FISHEYE' in [x["name"] for x in s["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "fisheye"
    elif 'MKX200' in [x["name"] for x in s["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "mkx200"

    scene["timeStamps"] = None

    actors = []
    for p in s["performers"]:
        # actors.append({"id":p["id"],"name":p["name"]})
        actors.append({"id": p["id"], "name": p["name"]})
    scene["actors"] = actors

    scene["fullVideoReady"] = True
    scene["fullAccess"] = True
    return jsonify(scene)

def filter():
    filter=['Recent','VR','2D']
    filter.extend(studios)
    filter.extend(performers)
    return filter

def rewrite_image_urls(scenes):
    for s in scenes:
        screenshot_url=s["paths"]["screenshot"]
        s["paths"]["screenshot"]='/image_proxy?scene_id='+screenshot_url.split('/')[4]+'&session_id='+screenshot_url.split('/')[5][11:]

@app.route('/image_proxy')
def image_proxy():
    scene_id = request.args.get('scene_id')
    session_id = request.args.get('session_id')
    url=app.config['GRAPHQL_API'][:-8]+'/scene/'+scene_id+'/screenshot?'+session_id
    r = requests.get(url,headers=headers)
    return Response(r.content,content_type=r.headers['Content-Type'])


@app.route('/')
def index():
    return redirect("/filter/Recent", code=302)

#    scenes = get_scenes_with_tag("export_deovr")
#    return render_template('index.html',filters=filter(),filter='Recent',scenes=scenes)
#    return show_category(filter='Recent')
@app.route('/filter/<string:filter_id>')
def show_category(filter_id):
    tags=[]
    scenes_filter={}
    if filter_id == 'Recent':
        scenes_filter={"tags": {"value": tags, "depth": 0, "modifier": "INCLUDES_ALL"}}
    elif filter_id == '2D':
        tags=[findTagIdWithName('export_deovr'),findTagIdWithName('FLAT')]
        scenes_filter={"tags": {"value": tags, "depth": 0, "modifier": "INCLUDES_ALL"}}
    elif filter_id == 'VR':
        tags=[findTagIdWithName('export_deovr'),findTagIdWithName('SBS')]
        scenes_filter={"tags": {"value": tags, "depth": 0, "modifier": "INCLUDES_ALL"}}
    elif filter_id in studios:
        studio_ids=[findStudioIdWithName(filter_id)]
        scenes_filter={"tags": {"depth": 0, "modifier": "INCLUDES_ALL","value": [findTagIdWithName('export_deovr')]},"studios":{"depth": 3,"modifier": "INCLUDES_ALL","value":studio_ids}}
    elif filter_id in performers:
        performer_ids=[findPerformerIdWithName(filter_id)]
        scenes_filter={"tags": {"depth": 0, "modifier": "INCLUDES_ALL","value": [findTagIdWithName('export_deovr')]},"performers":{"modifier": "INCLUDES_ALL","value":performer_ids}}

    scenes= get_scenes(scenes_filter)
    if 'ApiKey' in headers:
        rewrite_image_urls(scenes)

    return render_template('index.html',filters=filter(),filter=filter_id,scenes=scenes)

@app.route('/scene/<int:scene_id>')
def scene(scene_id):
    s = lookupScene(scene_id)
    if 'ApiKey' in headers:
        screenshot_url=s["paths"]["screenshot"]
        s["paths"]["screenshot"]='/image_proxy?scene_id='+screenshot_url.split('/')[4]+'&session_id='+screenshot_url.split('/')[5][11:]
        print(request.base_url)
    return render_template('scene.html',scene=s)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
