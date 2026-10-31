# Trabzon and campus geometry

Derived from OpenStreetMap via its public map API. © OpenStreetMap contributors.
Data is available under the Open Database License (ODbL) 1.0:
https://www.openstreetmap.org/copyright
https://opendatacommons.org/licenses/odbl/1-0/

The exact bounding box, retrieval timestamp and counts are in scene-source.json.
Only public way geometry and selected non-personal tags are retained. User/editor
names are not included. Building heights use OSM height where present, otherwise
OSM levels times an assumed 3m per floor, otherwise a 12m visual estimate.
The dataset is a visual campus model, not surveyed geometry or photogrammetry.

Regional building geometry (trabzon-buildings.geojson) follows the same ODbL terms.
The three public OSM extraction bounds, retrieval date and count are recorded in
trabzon-source.json. Campus building IDs are excluded to prevent duplicate extrusion.
Only 6 of the 7,916 additional heights come directly from the OSM height tag;
the other 7,910 use OSM levels x 3m or the 12m visual estimate.
