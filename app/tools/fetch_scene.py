"""Refresh bounded public OSM geometry for the campus scene, never synthetic buildings."""
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]/"web/data"
QUERY='[out:json][timeout:35];(way["building"](40.985,39.762,40.999,39.785);way["highway"](40.985,39.762,40.999,39.785);way["landuse"](40.985,39.762,40.999,39.785);way["leisure"](40.985,39.762,40.999,39.785););out tags geom;'

def convert(raw):
    features=[]
    for w in raw["elements"]:
        coords=[[p["lon"],p["lat"]] for p in w.get("geometry",[])]
        if len(coords)<2:continue
        tags=w.get("tags",{})
        closed=coords[0]==coords[-1] and len(coords)>=4
        kind="building" if tags.get("building") and closed else "road" if tags.get("highway") else "land" if closed else None
        if not kind:continue
        estimated=False
        try:height=float(tags["height"].replace("m","").strip());origin="OSM height"
        except (KeyError,ValueError):
            try:height=float(tags["building:levels"])*3;origin="OSM levels x 3m";estimated=True
            except (KeyError,ValueError):height=12;origin="12m visual estimate";estimated=True
        features.append({"type":"Feature","id":w["id"],"properties":{"kind":kind,"height":max(3,min(180,height)),"estimated":estimated,"height_source":origin,"name":tags.get("name",""),"class":tags.get("highway",tags.get("landuse",tags.get("leisure","")))},"geometry":{"type":"Polygon" if closed and kind!="road" else "LineString","coordinates":[coords] if closed and kind!="road" else coords}})
    return {"type":"FeatureCollection","features":features}

if __name__=="__main__":
    url="https://api.openstreetmap.org/api/0.6/map?bbox=39.765,40.988,39.780,40.997"
    request=Request(url,headers={"User-Agent":"GarbageCollectors-campus-demo/1.0"})
    with urlopen(request,timeout=40) as response:tree=ET.fromstring(response.read())
    nodes={n.attrib['id']:{'lon':float(n.attrib['lon']),'lat':float(n.attrib['lat'])} for n in tree.findall('node')}
    ways=[]
    for way in tree.findall('way'):
        tags={tag.attrib['k']:tag.attrib['v'] for tag in way.findall('tag')}
        if any(k in tags for k in ('building','highway','landuse','leisure')):
            ways.append({'id':int(way.attrib['id']),'tags':tags,'geometry':[nodes[n.attrib['ref']] for n in way.findall('nd') if n.attrib['ref'] in nodes]})
    geo=convert({'elements':ways})
    if not any(f["properties"]["kind"]=="building" for f in geo["features"]):raise RuntimeError("No buildings returned")
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/"campus.geojson").write_text(json.dumps(geo,ensure_ascii=False,separators=(',',':')),encoding="utf-8")
    counts={kind:sum(f["properties"]["kind"]==kind for f in geo["features"]) for kind in ("building","road","land")}
    (ROOT/"scene-source.json").write_text(json.dumps({"source":url,"license":"ODbL 1.0","copyright":"https://www.openstreetmap.org/copyright","fetched_at":datetime.now(timezone.utc).isoformat(),"counts":counts,"heights":"OSM height if available; levels x3m otherwise; missing heights estimated at12m. Not photogrammetry."},ensure_ascii=False,indent=2),encoding="utf-8")
    print(counts)
