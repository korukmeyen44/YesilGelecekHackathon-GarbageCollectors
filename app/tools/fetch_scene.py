"""Refresh bounded public OSM geometry for the campus scene, never synthetic buildings."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]/"web/data"


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

def fetch_osm(url):
    request=Request(url,headers={"User-Agent":"GarbageCollectors-campus-demo/1.0"})
    with urlopen(request,timeout=40) as response:tree=ET.fromstring(response.read())
    nodes={n.attrib['id']:{'lon':float(n.attrib['lon']),'lat':float(n.attrib['lat'])} for n in tree.findall('node')}
    ways=[]
    for way in tree.findall('way'):
        tags={tag.attrib['k']:tag.attrib['v'] for tag in way.findall('tag')}
        if any(k in tags for k in ('building','highway','landuse','leisure')):
            ways.append({'id':int(way.attrib['id']),'tags':tags,'geometry':[nodes[n.attrib['ref']] for n in way.findall('nd') if n.attrib['ref'] in nodes]})
    return convert({'elements':ways})


def fetch_trabzon():
    # Bounded extracts, not a bulk tile download. Existing campus stays independently usable.
    boxes=[('Ortahisar / Meydan','39.712,40.996,39.737,41.013'),
           ('Kalkınma / Üniversite','39.737,40.986,39.765,41.005'),
           ('KTÜ / Konaklar','39.765,40.983,39.793,41.005')]
    campus=json.loads((ROOT/'campus.geojson').read_text(encoding='utf-8'))
    existing={f['id'] for f in campus['features'] if f['properties']['kind']=='building'}
    features={};sources=[]
    for label,box in boxes:
        url='https://api.openstreetmap.org/api/0.6/map?bbox='+box
        geo=fetch_osm(url)
        for f in geo['features']:
            if f['properties']['kind']=='building' and f['id'] not in existing:features[f['id']]=f
        sources.append({'area':label,'url':url})
        print(label,len(features),flush=True)
    if not features:raise RuntimeError('No regional buildings returned; cache unchanged')
    data={'type':'FeatureCollection','features':list(features.values())}
    metadata={'sources':sources,'fetched_at':datetime.now(timezone.utc).isoformat(),
              'license':'ODbL 1.0','copyright':'https://www.openstreetmap.org/copyright',
              'building_count':len(features),'campus_buildings_excluded':True,
              'estimated_heights':sum(f['properties']['estimated'] for f in features.values()),
              'heights':'OSM height, otherwise levels x 3m, otherwise 12m estimate. Not photogrammetry.'}
    (ROOT/'trabzon-buildings.geojson').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (ROOT/'trabzon-source.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(metadata['building_count'],'regional buildings')


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trabzon',action='store_true',help='Expand cached buildings to Ortahisar, Kalkınma and Konaklar')
    args=parser.parse_args()
    if args.trabzon:
        fetch_trabzon()
        raise SystemExit(0)
    url="https://api.openstreetmap.org/api/0.6/map?bbox=39.765,40.988,39.780,40.997"
    geo=fetch_osm(url)
    if not any(f["properties"]["kind"]=="building" for f in geo["features"]):raise RuntimeError("No buildings returned")
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/"campus.geojson").write_text(json.dumps(geo,ensure_ascii=False,separators=(',',':')),encoding="utf-8")
    counts={kind:sum(f["properties"]["kind"]==kind for f in geo["features"]) for kind in ("building","road","land")}
    (ROOT/"scene-source.json").write_text(json.dumps({"source":url,"license":"ODbL 1.0","copyright":"https://www.openstreetmap.org/copyright","fetched_at":datetime.now(timezone.utc).isoformat(),"counts":counts,"heights":"OSM height if available; levels x3m otherwise; missing heights estimated at12m. Not photogrammetry."},ensure_ascii=False,indent=2),encoding="utf-8")
    print(counts)
