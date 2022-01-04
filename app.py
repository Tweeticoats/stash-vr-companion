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
tags_filters={}
tags_cache={}


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
    res= result["findScenes"]["scenes"]
    for s in res:
        scene_type(s)
        if 'ApiKey' in headers:
            rewrite_image_url(s)
    return res


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
    res= result["findScene"]
    scene_type(res)
    if 'ApiKey' in headers:
        rewrite_image_url(res)
    return res

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


def findPerformerWithID(id):
    query = """query findPerformer($performer_id: ID!){
  findPerformer(id: $performer_id){
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
    image_path
    tags{
      id
      name
    }
  }
}"""
    variables = {"performer_id": id}
    result = __callGraphQL(query, variables)
    return result['findPerformer']



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


def reload_filter_studios():
    query = """query {
      allStudios {
        id
        name
        details
      }
    }"""
    result = __callGraphQL(query)
    res=[]
    for s in result["allStudios"]:
        if s['details'] is not None and 'EXPORT_DEOVR' in s['details']:
            if s['name'] not in studios:
                studio_fiter={}
                studio_fiter['name']=s['name']
                studio_fiter['type']='STUDIO'
                studio_fiter['studio_id']=s['id']
#                studio_fiter['filter']={
#                    "tags": {"depth": 0, "modifier": "INCLUDES_ALL", "value": [tags_cache['export_deovr']['id']]},
#                    "studios": {"depth": 3, "modifier": "INCLUDES_ALL", "value": [s['id']]}}
                studio_fiter['filter'] = {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
                studio_fiter['post']=tag_cleanup_studio
                res.append(studio_fiter)
    return res

def reload_filter_performer():
    query = """{
  allPerformers{
  id
  name
  tags{
    id
    name
  }
}}"""
    result = __callGraphQL(query)
    res=[]
    for p in result["allPerformers"]:
        for tag in p['tags']:
            if tag["name"] == 'export_deovr':
                if p['name'] not in performers:
                    performer_filter = {}
                    performer_filter['name'] = p['name']
                    performer_filter['type'] = 'PERFORMER'
                    performer_filter['performer_id']=p['id']
#                    performer_filter['filter'] = {"tags": {"depth": 0, "modifier": "INCLUDES_ALL", "value": [tags_cache['export_deovr']['id']]},
#                                     "performers": {"modifier": "INCLUDES_ALL", "value": [p["id"]]}}
#                    tag_cleanup_performer
                    performer_filter['filter'] = {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
                    performer_filter['post'] = tag_cleanup_performer
                    res.append(performer_filter)
    return res

def reload_filter_tag():
    res=[]
    for f in tags_cache['export_deovr']['children']:
        tags_filter={}
        tags_filter['name']=f['name']
        tags_filter['type']='TAG'
        tags_filter['id']=f['id']
        tags_filter['filter']= {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
        tags_filter['post']=tag_cleanup
        res.append(tags_filter)
    return res

def tag_cleanup(scenes,filter):
    res=[]
    for s in scenes:
        if filter['id'] in [x['id']  for x in s['tags']]:
            res.append(s)
    return res

def tag_cleanup_3d(scenes,filter):
    res=[]
    for s in scenes:
        if s["is3d"]:
            res.append(s)
    return res

def tag_cleanup_2d(scenes,filter):
    res=[]
    for s in scenes:
        if not s["is3d"]:
            res.append(s)
    return res


def tag_cleanup_star(scenes,filter):
    res=[]
    for s in scenes:
        if s["rating"]==5:
            res.append(s)
    return res

def tag_cleanup_studio(scenes,filter):
    res=[]
    for s in scenes:
        if s["studio"] is not None and 'id' in s['studio']:
            if filter['studio_id'] == s['studio']['id']:
                res.append(s)
    return res

def tag_cleanup_performer(scenes,filter):
    res=[]
    for s in scenes:
        if filter['performer_id'] in [x['id'] for x in s['performers']]:
            res.append(s)
    return res



def scene_type(scene):
    if "180_180x180_3dh_LR" in scene["path"]:
        scene["is3d"] = True
        scene["screenType"] = "dome"
        scene["stereoMode"] = "sbs"
    else:
        scene["screenType"] = "flat"
        scene["is3d"] = False
    if 'SBS' in [x["name"] for x in scene["tags"]]:
        scene["stereoMode"] = "sbs"
    elif 'TB' in [x["name"] for x in scene["tags"]]:
        scene["stereoMode"] = "tb"

    if 'FLAT' in [x["name"] for x in scene["tags"]]:
        scene["screenType"] = "flat"
        scene["is3d"] = False
    elif 'DOME' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "dome"
    elif 'SPHERE' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "sphere"
    elif 'FISHEYE' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "fisheye"
    elif 'MKX200' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "mkx200"


def reload_filter_cache():
    query = """{
  allTags{
    id
    name
    children{
     id
      name
    }
  }
}"""
    result = __callGraphQL(query)
    if 'allTags' in result:
        tags_cache.clear()
    for t in result["allTags"]:
        tags_cache[t['name']]=t


def performer_update(self,performer):
    query="""
mutation performerUpdate($input: PerformerUpdateInput!) {
performerUpdate(input: $input) {
id
checksum
name
url
gender
twitter
instagram
birthdate
ethnicity
country
eye_color
height
measurements
fake_tits
career_length
tattoos
piercings
aliases
favorite
image_path
scene_count
stash_ids {
  endpoint
  stash_id
}
}
}
"""
    variables = {'input': performer}
    return self.__callGraphQL(query, variables)


def createTagWithName(name):
    query = """
mutation tagCreate($input:TagCreateInput!) {
tagCreate(input: $input){
id       
}
}
"""
    variables = {'input': {
        'name': name
    }}

    result = __callGraphQL(query, variables)
    return result["tagCreate"]["id"]


def filter():
    reload_filter_cache()

    recent_filter={}
    recent_filter['name']='Recent'
    recent_filter['filter'] = {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
    recent_filter['type']='BUILTIN'

    vr_filter ={}
    vr_filter['name']='VR'
    vr_filter['filter']={"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
    vr_filter['post']=tag_cleanup_3d
    vr_filter['type'] = 'BUILTIN'

    flat_filter={}
    flat_filter['name']='2D'
#    flat_filter['filter'] = {"tags": {"value": [tags_cache['export_deovr']['id'],tags_cache['FLAT']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
    flat_filter['filter']={"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
    flat_filter['post']=tag_cleanup_2d
    flat_filter['type'] = 'BUILTIN'

    star_filter={}
    star_filter['name']='5 Star'
#    star_filter['filter'] = {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"},"rating": {"modifier": "EQUALS","value": 5}}
    star_filter['filter']={"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
    star_filter['post']=tag_cleanup_star
    star_filter['type'] = 'BUILTIN'


    filter=[recent_filter,vr_filter,flat_filter,star_filter]

    for f in reload_filter_studios():
        filter.append(f)
    for f in reload_filter_performer():
        filter.append(f)
    for f in reload_filter_tag():
        filter.append(f)

#    reload_filter_performer()
#    filter.extend(studios)
#    filter.extend(performers)
#    reload_filter_tag()
#    filter.extend(tags_filters.keys())
    return filter

def rewrite_image_url(scene):
    screenshot_url=scene["paths"]["screenshot"]
    scene["paths"]["screenshot"]='/image_proxy?scene_id='+screenshot_url.split('/')[4]+'&session_id='+screenshot_url.split('/')[5][11:]


def setup():
    tags = ["VR", "SBS", "TB", "export_deovr", "FLAT", "DOME", "SPHERE", "FISHEYE", "MKX200"]
    reload_filter_cache()
    for t in tags:
        if t not in tags_cache.keys():
            print("creating tag " +t)
            createTagWithName(t)



@app.route('/deovr',methods=['GET', 'POST'])
def deovr():
    data = {}
    data["authorized"]="1"
    data["scenes"] = []

    all_scenes=None
    for f in filter():
        res=[]
#        scenes = get_scenes(f['filter'])
        if all_scenes is None:
            all_scenes = get_scenes(f['filter'])

        scenes = all_scenes
        if 'post' in f:
            var=f['post']
            scenes=var(scenes,f)

        for s in scenes:
            r = {}
            r["title"] = s["title"]
            r["videoLength"] = int(s["file"]["duration"])
#            if 'ApiKey' in headers:
#                screenshot_url = s["paths"]["screenshot"]
#                r["thumbnailUrl"] = request.base_url[:-6] + '/image_proxy?scene_id=' + screenshot_url.split('/')[
#                    4] + '&session_id=' + screenshot_url.split('/')[5][11:]
#            else:
#                r["thumbnailUrl"] = s["paths"]["screenshot"]
            r["thumbnailUrl"] = s["paths"]["screenshot"]
            r["video_url"] = request.base_url + '/' + s["id"]
            res.append(r)
        data["scenes"].append({"name": f['name'], "list": res})
    return jsonify(data)



@app.route('/deovr/<int:scene_id>')
def show_post(scene_id):
    s = lookupScene(scene_id)

    scene = {}
    scene["id"] = s["id"]
    scene["title"] = s["title"]
    scene["authorized"] = 1
    scene["description"] = s["details"]
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

    if "is3d" in s:
        scene["is3d"] = s["is3d"]
    if "screenType" in s:
        scene["screenType"] = s["screenType"]
    if "stereoMode" in s:
        scene["stereoMode"] = s["stereoMode"]

    scene["timeStamps"] = None

    actors = []
    for p in s["performers"]:
        # actors.append({"id":p["id"],"name":p["name"]})
        actors.append({"id": p["id"], "name": p["name"]})
    scene["actors"] = actors

    scene["fullVideoReady"] = True
    scene["fullAccess"] = True
    return jsonify(scene)




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
    filters=filter()
    for f in filters:
        if filter_id == f['name']:
            scenes = get_scenes(f['filter'])
            if 'post' in f:
                var=f['post']
                scenes=var(scenes,f)
            return render_template('index.html',filters=filters,filter=f,scenes=scenes)
    return "Error, filter does not exist"

@app.route('/scene/<int:scene_id>')
def scene(scene_id):
    s = lookupScene(scene_id)
    return render_template('scene.html',scene=s,filters=filter())

@app.route('/performer/<int:performer_id>')
def performer(performer_id):
    p=findPerformerWithID(performer_id)
    if 'export_deovr' in [x["name"] for x in p["tags"]]:
        p['isPinned']=True
    else:
        p['isPinned' ] = False
    return render_template('performer.html',performer=p,filters=filter())


@app.route('/gizmovr/<string:filter_id>')
def gizmovr_category(filter_id):
    tags=[]
    filters=filter()
    for f in filters:
        if filter_id == f['name']:
            scenes = get_scenes(f['filter'])
            if 'post' in f:
                var=f['post']
                scenes=var(scenes,f)

            base_path=request.base_url[:-len(request.path)]

            return render_template('gizmovr.html',filters=filters,filter=f,scenes=scenes,isGizmovr=True,base_path=base_path)
    return "Error, filter does not exist"


@app.route('/gizmovr_scene/<int:scene_id>')
def gizmovr_json(scene_id):
    s = lookupScene(scene_id)
    data ={}
    data["apiType"]="GIZMO"
    data["id"]=int(s["id"])
    data["title"] = s["title"]
    sources={"title":str(s["file"]["width"])+"p",
 #            "fps":s["file"]["framerate"],
 #            "size":s["file"]["size"],
 #            "bitrate":s["file"]["bitrate"],
 #            "width":s["file"]["width"],
#             "height": s["file"]["height"],
             "url":s["paths"]["stream"]+'.mp4'}
    data["sources"] = [sources]
#    data["imageThumb"]=s["paths"]["screenshot"]

    angle={}
    if s["is3d"]:
        if s["stereoMode"]=="tb":
            angle["framePacking"]="TB"
        else:
            angle["framePacking"] ="SBS"
        if s["screenType"] == "sphere":
            angle["angle"]="360"
        else:
            angle["angle"] = "180"
    else:
        angle["framePacking"]="NONE"
        angle["angle"]="FLAT"
    data["format"]=angle

    return jsonify(data)



setup()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
