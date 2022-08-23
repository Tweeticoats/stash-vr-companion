from flask import Flask,jsonify,render_template,request,Response,redirect,session
import requests
import json
import os
import datetime
import random
import copy
from threading import Timer
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from urllib3.exceptions import InsecureRequestWarning
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)

#app.config['SERVER_NAME'] = 'http://deovr.home'
app.config['GRAPHQL_API'] = os.getenv('API_URL', 'http://localhost:9999/graphql')
app.config['VERIFY_FLAG'] = not os.getenv('DISABLE_CERT_VERIFICATION', False)
# Disable insecure certificate verification warning when cert validation is disabled
if not app.config['VERIFY_FLAG']:
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

app.secret_key = 'N46XYWbnaXG6JtdJZxez'


headers = {
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Connection": "keep-alive",
    "DNT": "1"
}
if os.getenv('API_KEY'):
    headers['ApiKey']=os.getenv('API_KEY')
# This header is not technically correct, but will work around a bug with stash https://github.com/stashapp/stash/issues/2764
if app.config['GRAPHQL_API'].lower().startswith("https"):
    headers["X-Forwarded-Proto"] = "https"

studios=[]
performers=[]
tags_filters={}
tags_cache={}
config={}
cache_refresh_time=None
#scene_cache=[]
cache={"refresh_time":0,"scenes":[],"image_cache":{}}

image_dir = os.getenv('CACHE_DIR', './cache')
auth={}

needs_auth=False

def filter_studio(scenes,filter):
    return scenes

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

def tag_cleanup_interactive(scenes,filter):
    res=[]
    for s in scenes:
        if s["interactive"]:
            res.append(s)
    return res



def tag_cleanup_random(scenes,filter):
    if len(scenes) > 30:
        return random.sample(scenes,30)
    return scenes

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

def sort_scenes_date(scenes):
    return sorted(scenes,key=lambda x:x['date'] or '' ,reverse=True)

def sort_scenes_date_desc(scenes):
    return sorted(scenes,key=lambda x:x['date'] or '' )
def sort_scenes_updated_at(scenes):
    return sorted(scenes,key=lambda x:x['updated_at'] or '' ,reverse=True)

def sort_scenes_created_at(scenes):
    return sorted(scenes,key=lambda x:x['created_at'] or '' ,reverse=True)

def sort_scenes_title(scenes):
    return sorted(scenes,key=lambda x:x['title'] or '' ,reverse=True)

def sort_scenes_random(scenes):
    return random.sample(scenes,len(scenes))

sort_methods= {'date':sort_scenes_date,
'date_asc':sort_scenes_date_desc,
    'updated_at': sort_scenes_updated_at,
    'created_at': sort_scenes_created_at,
    'title': sort_scenes_title,
    'random': sort_scenes_random}

filter_methods= {'default':filter_studio,
    'tag':tag_cleanup,
    '2d': tag_cleanup_2d,
    '3d': tag_cleanup_3d,
    'star': tag_cleanup_star,
    'interactive': tag_cleanup_interactive,
    'studio': tag_cleanup_studio,
    'performer': tag_cleanup_performer,
    'random': tag_cleanup_random}

default_filters=[
    {'name':'Recent',
     'type':'BUILTIN',
     'filter_name':'default',
     'sort_name':'date',
     'enabled':True
     },
    {
        'name':'VR',
        'type': 'BUILTIN',
        'filter_name':'3d',
        'sort_name': 'date',
        'enabled':True
    },
    {
        'name': '2D',
        'type': 'BUILTIN',
        'filter_name': '2d',
        'sort_name': 'date',
        'enabled':True
    },
    {
        'name': 'Random',
        'type': 'BUILTIN',
        'filter_name': 'random',
        'sort_name': 'random',
        'enabled':True
    },
    {
        'name': 'Interactive',
        'type': 'BUILTIN',
        'filter_name': 'interactive',
        'sort_name': 'date',
        'enabled':True
    }]





def __callGraphQL(query, variables=None):
    json = {}
    json['query'] = query
    if variables != None:
        json['variables'] = variables

    # handle cookies
    response = requests.post(app.config['GRAPHQL_API'], json=json, headers=headers, verify=app.config['VERIFY_FLAG'])

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

def get_scenes(scene_filter, sort="updated_at",direction="DESC",per_page=100,page=1):
    query = """query findScenes($scene_filter: SceneFilterType!, $filter: FindFilterType) {
findScenes(scene_filter: $scene_filter filter: $filter ) {
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
  interactive
  updated_at
  created_at
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
    interactive_heatmap
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
  scene_markers{
    id
    title
    seconds
  }
}
}
}"""

    variables = {"scene_filter": scene_filter,"filter":{"sort": sort,"direction": direction,"page":page,"per_page": per_page}}
    result = __callGraphQL(query, variables)
    for s in result["findScenes"]["scenes"]:
        scene_type(s)
#        if 'ApiKey' in headers:
#            rewrite_image_url(s)
    return result


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
  interactive
  updated_at
  created_at
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
    interactive_heatmap
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
  scene_markers{
    id
    title
    seconds
  }
}
}"""
    variables = {"scene_id": id}
    result = __callGraphQL(query, variables)
    res= result["findScene"]
    scene_type(res)
#    if 'ApiKey' in headers:
#        rewrite_image_url(res)
    return res

def updateScene(self, sceneData):
    query = """mutation sceneUpdate($input:SceneUpdateInput!) {
    sceneUpdate(input: $input) {
    id
    }
}"""
    variables = {'input': sceneData}

    self.__callGraphQL(query, variables)



def findScene(id):
    for s in cache["scenes"]:
        if s["id"]==str(id):
            return s
    return None

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


def reload_studios():
    query = """query {
      allStudios {
        id
        name
        details
      }
    }"""
    result = __callGraphQL(query)
    res=[]
    studios.clear()
    for s in result["allStudios"]:
        studios.append(s)

def reload_filter_studios():
    reload_studios()
    for s in studios:
        if s['details'] is not None and 'EXPORT_DEOVR' in s['details']:
            if s['name'] not in [x['name'] for x in config['filters']]:
#            if s['name'] not in studios:
                studio_fiter={}
                studio_fiter['name']=s['name']
                studio_fiter['type']='STUDIO'
                studio_fiter['studio_id']=s['id']
#                studio_fiter['filter']={
#                    "tags": {"depth": 0, "modifier": "INCLUDES_ALL", "value": [tags_cache['export_deovr']['id']]},
#                    "studios": {"depth": 3, "modifier": "INCLUDES_ALL", "value": [s['id']]}}
#                studio_fiter['filter'] = {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
#                studio_fiter['post']=tag_cleanup_studio
                studio_fiter['filter_name'] = 'studio'
                studio_fiter['sort_name'] = 'date'
                studio_fiter['enabled'] = True
                config['filters'].append(studio_fiter)
#                res.append(studio_fiter)
        else:
            #check if the filter used to have the export_deovr tag but no longer does and remove it
            for f in config['filters']:
                if f['type'] == 'studio' and f['studio_id'] == s['id']:
                    config['filters'].remove(f)


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
        if p['name'] in [x['name'] for x in config['filters']]:
            if 'export_deovr' not in [x['name'] for x in p['tags']]:
            # Performer tag used to exist but no longer
                for f in config['filters']:
                    if f['type']=='PERFORMER' and f['performer_id']==p['id']:
                        config['filters'].remove(f)
        else:
            if 'export_deovr' in [x['name'] for x in p['tags']]:

#        for tag in p['tags']:
#            if tag["name"] == 'export_deovr':
#                if p['name'] not in performers:
                performer_filter = {}
                performer_filter['name'] = p['name']
                performer_filter['type'] = 'PERFORMER'
                performer_filter['performer_id']=p['id']
#                    performer_filter['filter'] = {"tags": {"depth": 0, "modifier": "INCLUDES_ALL", "value": [tags_cache['export_deovr']['id']]},
#                                     "performers": {"modifier": "INCLUDES_ALL", "value": [p["id"]]}}
#                    tag_cleanup_performer
#                performer_filter['filter'] = {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
#                performer_filter['post'] = tag_cleanup_performer
                performer_filter['filter_name']='performer'
                performer_filter['sort_name']='date'
                performer_filter['enabled']=True
                config['filters'].append(performer_filter)
#                    res.append(performer_filter)
    return res

def reload_filter_tag():
    res=[]
    for f in tags_cache['export_deovr']['children']:
        if f['name'] not in [x['name'] for x in config['filters']]:
            tags_filter={}
            tags_filter['name']=f['name']
            tags_filter['type']='TAG'
            tags_filter['id']=f['id']
    #        tags_filter['filter']= {"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}}
#            tags_filter['post']=tag_cleanup
            tags_filter['enabled']=True
            tags_filter['filter_name'] = 'tag'
            tags_filter['sort_name'] = 'date'
            config['filters'].append(tags_filter)

#        res.append(tags_filter)
#    return res



def scene_type(scene):
    if "180_180x180_3dh_LR" in scene["path"]:
        scene["is3d"] = True
        scene["screenType"] = "dome"
        scene["stereoMode"] = "sbs"
    elif "_MKX200" in scene["path"]:
        scene["is3d"] = True
        scene["screenType"] = "mkx200"
        scene["stereoMode"] = "sbs"
    elif "_FISHEYE190" in scene["path"]:
        scene["is3d"] = True
        scene["screenType"] = "rf52"
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
    elif 'MKX200' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "mkx200"
    elif '200°' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "mkx200"
    elif 'RF52' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "rf52"
    elif '190°' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "rf52"
    elif 'FISHEYE' in [x["name"] for x in scene["tags"]]:
        scene["is3d"] = True
        scene["screenType"] = "fisheye"

    if 'ApiKey' in headers:
        scene["heatmap"]='/heatmap_proxy/'+scene["id"]
    else:
        scene["heatmap"]=scene["paths"]["interactive_heatmap"]


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

def getStashConfig():
    query = """{
  configuration{
    general{
      username
      password
    }
  }
}"""
    result = __callGraphQL(query)
    return result


def createStudio(input):
    query="""mutation studioCreate($input: StudioCreateInput!) {
studioCreate(input: $input) {
id
name
}
}"""
    variables = {'input': input}
    result = __callGraphQL(query, variables)

def updateStudio(input):
    query="""mutation studioUpdate($input: StudioUpdateInput!) {
studioUpdate(input: $input) {
id
name
}
}"""
    variables = {'input': input}
    result = __callGraphQL(query, variables)


def filter():
    reload_filter_cache()
    filter=config['filters'].copy()
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
    if 'ApiKey' in headers:
        cfg=getStashConfig()
        auth['username']=cfg["configuration"]["general"]["username"]
        auth['password']=cfg["configuration"]["general"]["password"]
    reload_studios()
    print(str(studios))
    for s in studios:
        if s['name']=='vr-companion-config':
            config['config_studio']=int(s['id'])
            if len(s['details']) > 0:
                print("Loading config from stash: "+s['details'])
                config.update(json.loads(s['details']))
                print('final config:' +str(config))

    if 'filters' not in config:
        config['filters'] = default_filters


def isLoggedIn():
    if 'ApiKey' in headers:
        if 'username' in session:
            return True
        return False
    return True


def getFilter(filter_id):
    for f in config['filters']:
        if f['name']==filter_id:
            return f
    return None


@app.route('/deovr',methods=['GET', 'POST'])
def deovr():
    data = {}
    if 'ApiKey' in headers:
        if request.form:
            if request.form['login']==auth['username'] and bcrypt.check_password_hash(auth['password'], request.form['password']):
                data["authorized"] = "1"
            else:
                data["authorized"] = "-1"
                data["scenes"] = [{"name": "Login required", "list": []}]
                return jsonify(data)

        else:
            data["authorized"] = "-1"
            data["scenes"] = [{"name":"Login required","list":[]}]
            return jsonify(data)
    else:
         data["authorized"]="0"
    data["scenes"] = []




    all_scenes=None
    for f in config['filters']:
        if f['enabled']:
            res=[]
    #        scenes = get_scenes(f['filter'])
    #        if all_scenes is None:
    #            all_scenes = get_scenes(f['filter'])

    #        scenes = all_scenes
#            scenes=sort_scenes_date(cache['scenes'])
#            if 'post' in f:
#                var=f['post']
#                scenes=var(scenes,f)
            filter_func = filter_methods[f['filter_name']]
            sort_func = sort_methods[f['sort_name']]
            scenes = sort_func(filter_func(cache['scenes'], f))


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
    #            r["thumbnailUrl"] = request.url_root[:-1] +s["paths"]["screenshot"]
                r["thumbnailUrl"] = request.url_root[:-1] +s["image"]
    #            r["thumbnailUrl"] = '/image/' + s["id"]
                r["video_url"] = request.url_root + 'deovr/' + s["id"]
                res.append(r)
            data["scenes"].append({"name": f['name'], "list": res})
    return jsonify(data)



@app.route('/deovr/<int:scene_id>',methods=['GET', 'POST'])
def show_post(scene_id):
    s = findScene(scene_id)

    scene = {}
    scene["id"] = s["id"]
    scene["title"] = s["title"]
    scene["authorized"] = 1
    scene["description"] = s["details"]
#    scene["thumbnailUrl"] = request.url_root +s["paths"]["screenshot"]
#    scene["thumbnailUrl"] = '/image/' + s["id"]
#    scene["thumbnailUrl"] = request.url_root +'image/'+  s["id"]
    scene["thumbnailUrl"] = request.url_root[:-1] +s["image"]
    scene["videoPreview"] = s["paths"]["preview"]
    scene["isFavorite"] = False
    scene["isWatchlist"] = False

    vs = {}
    vs["resolution"] = s["file"]["height"]
    vs["height"] = s["file"]["height"]
    vs["width"] = s["file"]["width"]
    vs["size"] = s["file"]["size"]
    vs["url"] = s["paths"]["stream"]

    vs_mpg_StandardHd = {}
    vs_mpg_StandardHd["resolution"] = 720
    vs_mpg_StandardHd["height"] = 720
    vs_mpg_StandardHd["width"] = 1080
    vs_mpg_StandardHd["url"] = s["paths"]["stream"]+".mp4?resolution=STANDARD_HD"

    vs_mpg_FullHd = {}
    vs_mpg_FullHd["resolution"] = 1080
    vs_mpg_FullHd["height"] = 1080
    vs_mpg_FullHd["width"] = 1440
    vs_mpg_FullHd["url"] = s["paths"]["stream"]+".mp4?resolution=FULL_HD"

    vs_mpg_QuadHd = {}
    vs_mpg_QuadHd["resolution"] = 1440
    vs_mpg_QuadHd["height"] = 1440
    vs_mpg_QuadHd["width"] = 1920
    vs_mpg_QuadHd["url"] = s["paths"]["stream"]+".mp4?resolution=QUAD_HD"

    vs_mpg_VrHd = {}
    vs_mpg_VrHd["resolution"] = 1920
    vs_mpg_VrHd["height"] = 1920
    vs_mpg_VrHd["width"] = 2160
    vs_mpg_VrHd["url"] = s["paths"]["stream"]+".mp4?resolution=VR_HD"

    vs_mpg_FourK = {}
    vs_mpg_FourK["resolution"] = 2160
    vs_mpg_FourK["height"] = 2160
    vs_mpg_FourK["width"] = 2880
    vs_mpg_FourK["url"] = s["paths"]["stream"]+".mp4?resolution=FOUR_K"




    wmshd = {}
    wmshd["resolution"] = 720
    wmshd["height"] = 1440
    wmshd["width"] = 720
    wmshd["url"] = s["paths"]["stream"]+".webm?resolution=STANDARD_HD"

    wmfhd = {}
    wmfhd["resolution"] = 1080
    wmfhd["height"] = 2160
    wmfhd["width"] = 1080
    wmfhd["url"] = s["paths"]["stream"]+".webm?resolution=FULL_HD"

    scene["encodings"] = [{"name": "mp4", "videoSources": [vs_mpg_StandardHd,vs_mpg_FullHd,vs_mpg_QuadHd,vs_mpg_VrHd,vs_mpg_FourK]},{"name": "webm", "videoSources": [wmshd,wmfhd]},{"name": "stream", "videoSources": [vs]}]

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

    if s["interactive"]:
        scene["isScripted"] = True
        scene["fleshlight"]=[{"title": Path(s['path']).stem +'.funscript',"url": s["paths"]["funscript"]}]

        if 'ApiKey' in headers:
            scene["fleshlight"] = [{"title": Path(s['path']).stem + '.funscript', "url": request.url_root+'script_proxy/'+s['id']}]
        else:
            scene["fleshlight"] = [{"title": Path(s['path']).stem + '.funscript', "url": s["paths"]["funscript"]}]

    else:
        scene["isScripted"] = False
    if "scene_markers" in s:
        ts=[]
        for m in s["scene_markers"]:
            ts.append({"ts":m["seconds"],"name":m["title"]})
        scene["timeStamps"]=ts
    scene["videoLength"]= int(s["file"]["duration"])

    return jsonify(scene)




@app.route('/image_proxy')
def image_proxy():
    scene_id = request.args.get('scene_id')
    session_id = request.args.get('session_id')
    url=app.config['GRAPHQL_API'][:-8]+'/scene/'+scene_id+'/screenshot?'+session_id
    r = requests.get(url, headers=headers, verify=app.config['VERIFY_FLAG'])
    return Response(r.content,content_type=r.headers['Content-Type'])

@app.route('/script_proxy/<int:scene_id>')
def script_proxy(scene_id):
    s = lookupScene(scene_id)
    r = requests.get(s["paths"]["funscript"],headers=headers, verify=app.config['VERIFY_FLAG'])
    return Response(r.content,content_type=r.headers['Content-Type'])

@app.route('/heatmap_proxy/<int:scene_id>')
def heatmap_proxy(scene_id):
    s = lookupScene(scene_id)
    r = requests.get(s["paths"]["interactive_heatmap"],headers=headers, verify=app.config['VERIFY_FLAG'])
    return Response(r.content,content_type=r.headers['Content-Type'])


@app.route('/')
def index():
    return redirect("/filter/Recent", code=302)

#    scenes = get_scenes_with_tag("export_deovr")
#    return render_template('index.html',filters=filter(),filter='Recent',scenes=scenes)
#    return show_category(filter='Recent')
@app.route('/filter/<string:filter_id>',methods=['GET', 'POST'])
def show_category(filter_id):
    if not isLoggedIn():
        return redirect("/login", code=302)
    f= getFilter(filter_id)
    if f is None:
        return "Error, filter does not exist"

    if 'enable' in request.args:
        if request.args.get('enable')=='True':
            f['enabled']=True
        elif request.args.get('enable')=='False':
            f['enabled']=False
        saveConfig()
    if 'sort_name' in request.form:
        sort_name=request.form['sort_name']
        f['sort_name']=sort_name
#        f['sort']=sort_methods[sort_name]
        print(f)
        saveConfig()

    session['mode']='deovr'
    tags=[]
    if filter_id == f['name']:
#            scenes = get_scenes(f['filter'])
#        scenes=cache['scenes']

#        print (f)
#        if 'post' in f:
        filter_func=filter_methods[f['filter_name']]
        sort_func=sort_methods[f['sort_name']]

        scenes=sort_func(filter_func(cache['scenes'],f))
#        print(f)
#            var=f['sort']
#            scenes=var(scenes,f)
        session['filter']=f['name']
        return render_template('index.html',filters=config['filters'],filter=f,isGizmovr=False,scenes=scenes,sort_methods=sort_methods.keys())
    return "error?"


@app.route('/scene/<int:scene_id>')
def scene(scene_id):
    if not isLoggedIn():
        return redirect("/login", code=302)

    s = findScene(scene_id)
    return render_template('scene.html',scene=s,filters=config['filters'])

@app.route('/performer/<int:performer_id>')
def performer(performer_id):
    if not isLoggedIn():
        return redirect("/login", code=302)

    p=findPerformerWithID(performer_id)
    if 'export_deovr' in [x["name"] for x in p["tags"]]:
        p['isPinned']=True
    else:
        p['isPinned' ] = False
    scenes=[]
    for s in cache["scenes"]:
        if performer_id in [int(x["id"]) for x in s["performers"]]:
            scenes.append(s)
        print(str(s["performers"]))
#    print(scenes)
    return render_template('performer.html',performer=p,filters=config['filters'],scenes=scenes)


@app.route('/gizmovr/<string:filter_id>')
def gizmovr_category(filter_id):
    session['mode']='gizmovr'
    tags=[]
    filters=config['filters']
    for f in filters:
        if filter_id == f['name']:
#            scenes = get_scenes(f['filter'])
#            if 'post' in f:
#                var=f['post']
#                scenes=var(scenes,f)
            filter_func = filter_methods[f['filter_name']]
            sort_func = sort_methods[f['sort_name']]

            scenes = sort_func(filter_func(cache['scenes'], f))

            session['filter']=f['name']
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

@app.route('/stash-metadata')
def stash_metadata():

    filter = {}
    scenes=get_scenes(filter)
    data = {}
    data["timestamp"] = datetime.datetime.now().isoformat() + "Z"
    data["bundleVersion"] = "1"
    data2 = []
    index = 1

    if scenes is not None:
        for s in scenes:
            index = index + 1
            r = {}
            r["_id"] = str(index)
            r["scene_id"] = s["id"]

            r["title"] = s["title"]
            if "studio" in s:
                if s["studio"]:
                    r["studio"] = s["studio"]["name"]
            if s["is3d"]:
                r["scene_type"]="VR"
            else:
                r["scene_type"]="2D"

            if "screenType" in s:
                r["screenType"] = s["screenType"]
            if "stereoMode" in s:
                r["stereoMode"] = s["stereoMode"]

            r["gallery"] = None
            tags = []
            if "tags" in s:
                for t in s["tags"]:
                    tags.append(t["name"])
            r["tags"] = tags

            performer = []
            if "performers" in s:
                for t in s["performers"]:
                    performer.append(t["name"])
            r["cast"] = performer
            path = s["path"][s["path"].rindex('/') + 1:]
            r["filename"] = [path]
            r["synopsis"] = s["details"]
            r["released"] = s["date"]
            r["homepage_url"] = s["url"]
            r["covers"]=[s["paths"]["screenshot"]]

            data2.append(r)

    data["scenes"] = data2
    return jsonify(data)
@app.route('/info')
def info():
    refresh_time=datetime.now()-cache['refresh_time']
    res="cache refreshed "+str(refresh_time.total_seconds())+" seconds ago."
    res=res+"cache size="+str(len(cache['scenes']))+"<br/>"

    res=res+"image cache: "+str(cache['image_cache'])+"<br/>"
    res=res+"scenes: " +str (cache['scenes'])+'<br/>'
    res=res+"config: " +str(config)

    res=res+"is logged in:"+str(isLoggedIn())
    return res
@app.route('/clear-cache')
def clearCache():
    refreshCache()
    return redirect("/filter/Recent", code=302)



def refreshCache():
    print("Cache currently contains",len(cache['scenes']))
    print("refreshing cache")
    reload_filter_cache()

    cache['refresh_time']=datetime.now()


    if len(cache['scenes']) ==0:
        scenes=[]
        per_page=100
        print("Fetching "+str(per_page)+" scenes")
        res=get_scenes(scene_filter={"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}},sort="updated_at",direction="DESC",page=1,per_page=100)
        scenes=res["findScenes"]["scenes"]
        if res["findScenes"]["count"] > per_page:
            for x in range (2,(res["findScenes"]["count"]//per_page +2)):
                print("Fetching " + str(x*per_page) + " scenes")
                res = get_scenes(scene_filter={
                    "tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}},
                                 sort="updated_at", direction="DESC", page=x, per_page=per_page)
                scenes.extend(res["findScenes"]["scenes"])
        cache['scenes']=scenes
        if len(scenes)> 0:
            cache['last_updated']=datetime.fromisoformat(scenes[0]["updated_at"].replace("Z",""))
        else:
            cache['last_updated']=cache['refresh_time']
    else:
        #check the last updated scene
        res=get_scenes(scene_filter={"tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}},sort="updated_at",direction="DESC",page=1,per_page=1)
        if res["findScenes"]["count"] > 0:
            updated_at=datetime.fromisoformat(res["findScenes"]["scenes"][0]["updated_at"].replace("Z",""))
            if updated_at > cache['last_updated'] or len(cache["scenes"]) != res["findScenes"]["count"]:
                print("Cache needs updating")
                scenes = []
                per_page = 100
                print("Fetching " + str(per_page) + " scenes")
                res = get_scenes(scene_filter={
                    "tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}},
                                 sort="updated_at", direction="DESC", page=1, per_page=100)
                scenes = res["findScenes"]["scenes"]
                if res["findScenes"]["count"] > per_page:
                    for x in range(2, (res["findScenes"]["count"] // per_page + 2)):
                        print("Fetching " + str(x * per_page) + " scenes")
                        res = get_scenes(scene_filter={
                            "tags": {"value": [tags_cache['export_deovr']['id']], "depth": 0, "modifier": "INCLUDES_ALL"}},
                            sort="updated_at", direction="DESC", page=x, per_page=per_page)
                        scenes.extend(res["findScenes"]["scenes"])
                cache['scenes'] = scenes
                cache['last_updated'] = updated_at
            else:
                print("Cache up to date")



    print("Cache currently contains ",len(cache['scenes'])," scenes, checking image cache")

    modified=False
    for index, s in enumerate(cache['scenes']):
        if not os.path.exists(os.path.join(image_dir, s['id'])):
            print("fetching image: " + s['id'])
            screenshot = s['paths']['screenshot']
            r = requests.get(screenshot, headers=headers, verify=app.config['VERIFY_FLAG'])
            with open(os.path.join(image_dir, s['id']), "xb") as f:
                f.write(r.content)
                f.close()
                cache['image_cache'][s['id']] = {"file": os.path.join(image_dir, s['id']),
                                                 "mime": r.headers['Content-Type'], "updated": s["updated_at"]}
#                cache['scenes'][index]["paths"]["screenshot"] = '/image/' + str(s['id'])
                cache['scenes'][index]["image"] = '/image/' + str(s['id'])
                modified = True
        else:
            if s['id'] in cache['image_cache']:
                if s["updated_at"] != cache['image_cache'][s['id']]["updated"]:

                    screenshot = s['paths']['screenshot']
                    print(screenshot)

                    r = requests.get(screenshot, headers=headers, verify=app.config['VERIFY_FLAG'])
                    with open(os.path.join(image_dir, s['id']), "wb") as f:
                        f.write(r.content)
                        f.close()
                        modified=True
                    cache['scenes'][index]["image"] = '/image/' + str(s['id'])
                    cache['image_cache'][s['id']]["updated"]=s["updated_at"]
                else:
                    cache['scenes'][index]["image"] = '/image/' + str(s['id'])
                    cache['image_cache'][s['id']]["updated"]=s["updated_at"]
            else:
#                cache['scenes'][index]["image"] = '/image/' + str(s['id'])
#                cache['image_cache'][s['id']]["updated"] = ["updated_at"]
#                cache['scenes'][index]["paths"]["screenshot"] = '/image/' + str(s['id'])
                r = requests.get(s['paths']['screenshot'], headers=headers, verify=app.config['VERIFY_FLAG'])
                with open(os.path.join(image_dir, s['id']), "wb") as f:
                    f.write(r.content)
                    f.close()
                    modified=True
                    print("Replacing image: "+s['paths']['screenshot'])
                    cache['scenes'][index]["image"] = '/image/' + str(s['id'])
                    cache['image_cache'][s['id']] = {"file": os.path.join(image_dir, s['id']),
                                                     "mime": r.headers['Content-Type'], "updated": s["updated_at"]}

    reload_filter_studios()
    reload_filter_performer()
    reload_filter_tag()

    if modified:
        save_index()
    print("Finished Cache Refresh")



def setup_image_cache():
    if not os.path.exists(image_dir):
        os.mkdir(image_dir)
    if os.path.exists(os.path.join(image_dir,"index.json")):
        print("loading cache index")
        with open(os.path.join(image_dir,"index.json")) as f:
            cache['image_cache']=json.load(f)
            print("loaded cache index" +str(len(cache['image_cache'])))

def save_index():
    with open(os.path.join(image_dir, "index.json"), 'w') as f:
        json.dump(cache['image_cache'], f)
        print("saved cache index")


def saveConfig():


    print('Saving config: '+str(config))
    print(config)
    if 'config_studio' in config:
        input = {"id":config['config_studio'],"name": "vr-companion-config", "details":json.dumps(config)}
        status=updateStudio(input)
    else:
        input = {"name": "vr-companion-config","details":json.dumps(config)}
        res=createStudio(input)
#        config['config_studio']=res['id']

@app.route('/image/<int:scene_id>')
def images(scene_id):
    if str(scene_id) in cache['image_cache']:
        with open(cache['image_cache'][str(scene_id)]["file"],'rb') as f:
            image=f.read()
            return Response(image,content_type=cache['image_cache'][str(scene_id)]["mime"])
    return "image not in cache"




@app.route('/heresphere',methods=['GET', 'POST'])
def heresphere():
    data = {}

    if 'ApiKey' in headers and request.method == 'POST':

        if request.json['username']==auth['username'] and bcrypt.check_password_hash(auth['password'], request.json['password']):
            data["access"] = "1"
        elif 'Auth-Token' in request.headers:
            if request.headers['Auth-Token']==headers['ApiKey']:
                data["access"]=1
            else:
                return jsonify({"access": "-1", "library": []}), {"HereSphere-JSON-Version": 1}
        else:
            return jsonify({"access": "-1","library":[]}),{"HereSphere-JSON-Version":1}
    else:
        data["access"] = "0"


#    data["banner"]={"image": "https://www.example.com/heresphere/banner.png","link":""}
    data["library"] = []

    all_scenes=None
    for f in config['filters']:
        if f['enabled']:
            filter_func = filter_methods[f['filter_name']]
            sort_func = sort_methods[f['sort_name']]
            scenes = sort_func(filter_func(cache['scenes'], f))

            #            if 'post' in f:
#               var=f['post']
#                scenes=var(cache['scenes'],f)
            data["library"].append({"name": f['name'], "list": [request.url_root + 'heresphere/' + s["id"] for s in scenes]})
    return jsonify(data),{"HereSphere-JSON-Version":1}

@app.route('/heresphere/auth',methods=['POST'])
def heresphere_auth():
    data = {}
    if 'ApiKey' in headers and request.method == 'POST':

        print("here: "+str(request.json)+request.json['username']+"-"+request.json['username'])
        if request.json['username']==auth['username'] and bcrypt.check_password_hash(auth['password'], request.json['password']):
            data["access"] = "1"
            data["auth-token"]=headers['ApiKey']
            print("Successful login")
        else:
            return jsonify({"access": "-1","library":[]}),{"HereSphere-JSON-Version":1}
    return jsonify(data), {"HereSphere-JSON-Version": 1}


@app.route('/heresphere/<int:scene_id>',methods=['GET', 'POST'])
def heresphere_scene(scene_id):
    scene = {}
    if 'ApiKey' in headers and request.method == 'POST':

        print("scene: "+str(request.json)+request.json['username']+"-"+request.json['username'])
        if request.json['password']==headers['ApiKey']:
            scene["access"] = "1"
            print("Successful login")
        elif 'Auth-Token' in request.headers:
            if request.headers['Auth-Token']==headers['ApiKey']:
                scene["access"] = "1"
            else:
                return jsonify({"access": "-1"}), {"HereSphere-JSON-Version": 1}
        else:
            return jsonify({"access": "-1"}),{"HereSphere-JSON-Version":1}
    else:
        scene["access"] = "0"


    s=findScene(scene_id)

#    content = request.get_json(silent=True)
#    if content:
#        if "isFavorite" in content:
#            cene(s)



#    scene["id"] = s["id"]
    scene["title"] = s["title"]
    scene["description"] = s["details"]
    scene["thumbnailImage"] = request.url_root[:-1] +s["image"]
    scene["thumbnailVideo"] = s["paths"]["preview"]
    scene["dateReleased"]=s["date"]
    scene["dateAdded"] = s["date"]
    scene["duration"]= int(s["file"]["duration"])
    scene["favorites"]=0
    scene["comments"]=0
    scene["isFavorite"]=False
    if s["rating"]:
        scene["rating"]=s["rating"]
        if s["rating"]==5:
            scene["isFavorite"] = True
    else:
        scene["rating"]=0

    vs = {}
    vs["resolution"] = s["file"]["height"]
    vs["height"] = s["file"]["height"]
    vs["width"] = s["file"]["width"]
    vs["size"] = s["file"]["size"]
    vs["url"] = s["paths"]["stream"]

    scene["media"] = [{"name": "stream", "sources": [vs]}]

    if "screenType" in s:
        scene["projection"] = s["screenType"]
    if "stereoMode" in s:
        scene["stereo"] = s["stereoMode"]

    if s["is3d"]:
        if s["stereoMode"]=="tb":
            scene["stereo"]="tb"
        else:
            scene["stereo"] ="sbs"
        if s["screenType"] == "sphere":
            scene["projection"]="equirectangular360"
        elif s["screenType"] == "mkx200":
            scene["projection"]="fisheye"
            scene["lens"]="MKX220"
        elif s["screenType"] == "rf52":
            scene["projection"]="fisheye"
            scene["lens"]="rf52"

        else:
            scene["projection"] = "equirectangular"
    else:
        scene["projection"]="perspective"
        scene["stereo"]="mono"




    tags=[]


    for t in s["tags"]:
        tags.append({"name":t["name"],"start":0,"end":0,"track":0,"rating":0})
    if "scene_markers" in s:
        for m in s["scene_markers"]:
            tags.append({"start":m["seconds"],"end":0,"name":m["title"],"track":0,"rating":0})

    for p in s["performers"]:
        # actors.append({"id":p["id"],"name":p["name"]})
        tags.append( {"name": "Talent:"+p["name"],"track":1,"start":0,"end":0,"rating":0})
    if s["studio"]:
        tags.append({"name":"Studio:"+s["studio"]["name"],"track":2,"start":0,"end":0,"rating":0})

    if s["interactive"]:
        if 'ApiKey' in headers:
            scene["scripts"] = [{"name": Path(s['path']).stem + '.funscript', "url": request.url_root+'script_proxy/'+s['id'], "rating": 1}]
        else:
            scene["scripts"]=[{"name": Path(s['path']).stem +'.funscript',"url": s["paths"]["funscript"],"rating":1}]

    scene["tags"]=tags


    return jsonify(scene),{"HereSphere-JSON-Version":1}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        print(request.form['username'] + auth['username'])
        if request.form['username']==auth['username']:
            if bcrypt.check_password_hash(auth['password'], request.form['password']):
                session['username'] = request.form['username']
                return redirect("/filter/Recent", code=302)
    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('username', None)
    return redirect("/login", code=302)






setup()
setup_image_cache()
refreshCache()


sched = BackgroundScheduler(daemon=True)
sched.add_job(refreshCache,'interval',minutes=5)
sched.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
