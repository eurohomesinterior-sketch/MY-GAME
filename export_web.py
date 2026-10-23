"""
Export the road and the STC Coach as compressed web models for the browser game in web/.

  & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background --python export_web.py

Reads export/accra_kumasi_road.blend and the bus file (both untouched) and writes web/assets/:
road.glb, terrain.glb, town.glb, trees.glb, trees_far.glb, bus.glb (Draco), route.json, manifest.json.
The bus is exported at rest with simple node names the game animates:
BusRoot (travel), BusBody (lean), Steer_FL/FR, Wheel_FL/FR/RL/RR.
"""
import json
import os
import shutil
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "web", "assets")
os.makedirs(OUT, exist_ok=True)
ROAD = os.path.join(HERE, "export", "accra_kumasi_road.blend")
BUS = os.path.join(os.path.expanduser("~"), "Documents", "ChatGPT", "boss 2", "STC Coach - Smooth Drive.blend")

GROUPS = {
    "road": ("Road_", "Markings_", "Terminals", "Terminal_Markings"),
    "terrain": ("Terrain_",),
    "town": ("Buildings_", "Signs", "Bus_Stops"),
    "trees": ("Trees_",),
    "trees_far": ("TreesFar_",),
}


def export(name, objects, quant=18):
    for ob in bpy.data.objects:
        ob.select_set(False)
    for ob in objects:
        ob.select_set(True)
    path = os.path.join(OUT, name + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
        export_texcoords=False, export_normals=True, export_cameras=False, export_lights=False,
        export_animations=False, export_extras=False,
        export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
        export_draco_position_quantization=quant, export_draco_normal_quantization=10)
    print("EXPORTED", name, len(objects), "objects", round(os.path.getsize(path) / 1e6, 2), "MB")
    return os.path.getsize(path)


sizes = {}

# ---------------------------------------------------------------- road scene
bpy.ops.wm.open_mainfile(filepath=ROAD)
for name, prefixes in GROUPS.items():
    objs = [ob for ob in bpy.data.objects if ob.type == 'MESH' and ob.name.startswith(prefixes)]
    sizes[name] = export(name, objs)

# ---------------------------------------------------------------- bus
bpy.ops.wm.open_mainfile(filepath=BUS)
O = bpy.data.objects
RIG = {
    "CTRL BUS - move and rotate entire vehicle": "BusMaster",
    "CTRL TRAVEL - driven by Distance": "BusRoot",
    "CTRL BODY - suspension pitch and roll": "BusBody",
}
for lab, short in (("FRONT LEFT", "FL"), ("FRONT RIGHT", "FR"), ("REAR LEFT", "RL"), ("REAR RIGHT", "RR")):
    RIG["CTRL %s - suspension" % lab] = "Susp_" + short
    RIG["CTRL %s - steering" % lab] = "Steer_" + short
    RIG["CTRL %s - wheel rotation" % lab] = "Wheel_" + short
keep_colls = {"01 BODY", "02 GLAZING", "03 WHEELS", "04 DETAILS", "05 LIVERY", "10 CABIN INTERIOR"}

# rest pose: no animation or drivers, every control at zero
rig = [O[n] for n in RIG]
for ob in rig:
    ob.animation_data_clear()
master = O["CTRL BUS - move and rotate entire vehicle"]
for k in list(master.keys()):
    if isinstance(master[k], float) and k not in ("Wheel radius", "Auto wheel roll"):
        master[k] = 0.0
for ob in rig:
    ob.rotation_euler = (0.0, 0.0, 0.0)
O["CTRL TRAVEL - driven by Distance"].location = (0.0, 0.0, 0.0)
O["CTRL BODY - suspension pitch and roll"].location = (0.0, 0.0, 1.8)
for lab in ("FRONT LEFT", "FRONT RIGHT", "REAR LEFT", "REAR RIGHT"):
    O["CTRL %s - suspension" % lab].location.z = 0.68
    O["CTRL %s - steering" % lab].location = (0.0, 0.0, 0.0)
    O["CTRL %s - wheel rotation" % lab].location = (0.0, 0.0, 0.0)
bpy.context.view_layer.update()

# bake modifiers / text into plain meshes, then merge each rig part into one mesh
dg = bpy.context.evaluated_depsgraph_get()
parts = {}
for ob in list(O):
    coll = ob.users_collection[0].name if ob.users_collection else ""
    if coll not in keep_colls or ob.type not in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META'}:
        continue
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    new = bpy.data.objects.new(ob.name + " baked", me)
    bpy.context.scene.collection.objects.link(new)
    new.parent = ob.parent
    new.matrix_world = ob.matrix_world.copy()
    parts.setdefault(ob.parent.name if ob.parent else "", []).append(new)
for ob in list(O):
    if ob not in rig and not ob.name.endswith(" baked"):
        bpy.data.objects.remove(ob)
merged = []
for parent_name, objs in parts.items():
    active = objs[0]
    with bpy.context.temp_override(active_object=active, object=active, selected_objects=objs,
                                   selected_editable_objects=objs):
        bpy.ops.object.join()
    active.name = (RIG.get(parent_name, "Bus") + "Mesh").replace("BusBodyMesh", "BusBodyMesh")
    merged.append(active)
for old, new in RIG.items():
    O[old].name = new
print("BUS PARTS", [(m.name, m.parent.name if m.parent else None, len(m.data.polygons)) for m in merged])
sizes["bus"] = export("bus", rig + merged, quant=14)

# ---------------------------------------------------------------- data for the game
shutil.copy(os.path.join(HERE, "export", "route.json"), os.path.join(OUT, "route.json"))
json.dump({"files": {k + ".glb": v for k, v in sizes.items()}}, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
print("WEB EXPORT DONE", {k: round(v / 1e6, 2) for k, v in sizes.items()})
