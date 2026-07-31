# Build rooftop VAV AHUs + cartoon drone for Vibe 21 Unity twin.
# Run in Blender (GUI) via MCP execute_blender_code or:
#   blender --python build_twin_roof_assets.py
#
# Exports FBX under unity/liberty_100/Assets/Models/Twin/

import bpy
import math
from pathlib import Path

OUT = Path(r"C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_21\unity\liberty_100\Assets\Models\Twin")
OUT.mkdir(parents=True, exist_ok=True)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def mat(name, rgba, metallic=0.35, rough=0.45):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = rough
    return m


def prim(name, typ, loc, scale, material, parent=None):
    if typ == "cube":
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    elif typ == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1, location=loc)
    elif typ == "uv":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=loc)
    elif typ == "cone":
        bpy.ops.mesh.primitive_cone_add(radius1=0.5, depth=1, location=loc)
    else:
        raise ValueError(typ)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    return obj


def build_vav_ahu(root_name, label):
    """Central VAV AHU look: cabinet + OA hood + supply fan wheel + exhaust cowl."""
    empty = bpy.data.objects.new(root_name, None)
    bpy.context.collection.objects.link(empty)
    empty["entity_hint"] = root_name
    empty["ahu_type"] = "VAV_CHW"  # from IDF AirLoopHVAC VAV Sys + Coil:Cooling:Water
    empty["airloop"] = label

    steel = mat(f"{root_name}_steel", (0.55, 0.58, 0.62, 1), 0.55, 0.35)
    accent = mat(f"{root_name}_accent", (0.15, 0.35, 0.55, 1), 0.2, 0.5)
    fan_m = mat(f"{root_name}_fan", (0.2, 0.2, 0.22, 1), 0.6, 0.3)
    warn = mat(f"{root_name}_warn", (0.85, 0.55, 0.1, 1), 0.1, 0.5)

    cab = prim(f"{root_name}_Cabinet", "cube", (0, 0, 0.7), (4.2, 2.4, 1.4), steel, empty)
    prim(f"{root_name}_OAHood", "cube", (-1.6, 0, 1.55), (1.2, 1.6, 0.35), accent, empty)
    prim(f"{root_name}_FilterDoor", "cube", (0.2, 1.22, 0.7), (1.6, 0.08, 0.9), warn, empty)
    prim(f"{root_name}_CoilSection", "cube", (1.3, 0, 0.7), (1.0, 2.2, 1.2), accent, empty)
    # Discharge plenum
    prim(f"{root_name}_Discharge", "cube", (2.4, 0, 0.55), (0.7, 1.4, 0.9), steel, empty)

    # Supply fan wheel (animated in Unity)
    fan = prim(f"{root_name}_FanWheel", "cyl", (0.9, 0, 0.75), (1.1, 1.1, 0.25), fan_m, empty)
    fan.rotation_euler = (math.radians(90), 0, 0)
    # blades as thin boxes
    for i in range(6):
        ang = i * (math.pi / 3)
        blade = prim(f"{root_name}_Blade_{i}", "cube", (0.9 + 0.35 * math.cos(ang), 0.35 * math.sin(ang), 0.75),
                     (0.55, 0.08, 0.12), fan_m, fan)

    # Exhaust / relief cowl
    prim(f"{root_name}_ReliefCowl", "cyl", (-0.4, -0.9, 1.7), (0.7, 0.7, 0.5), steel, empty)
    # Nameplate cube
    plate = prim(f"{root_name}_Nameplate", "cube", (0, -1.22, 0.9), (1.8, 0.05, 0.35), warn, empty)
    return empty


def build_drone(root_name="TwinDrone"):
    empty = bpy.data.objects.new(root_name, None)
    bpy.context.collection.objects.link(empty)
    body_m = mat(f"{root_name}_body", (0.12, 0.55, 0.35, 1), 0.15, 0.4)
    arm_m = mat(f"{root_name}_arm", (0.25, 0.25, 0.28, 1), 0.4, 0.4)
    prop_m = mat(f"{root_name}_prop", (0.9, 0.9, 0.2, 1), 0.1, 0.35)

    prim(f"{root_name}_Body", "uv", (0, 0, 0), (0.55, 0.35, 0.25), body_m, empty)
    prim(f"{root_name}_Cam", "uv", (0.25, 0, -0.15), (0.12, 0.12, 0.12), arm_m, empty)

    props = []
    for i, (x, y) in enumerate(((0.55, 0.55), (0.55, -0.55), (-0.55, 0.55), (-0.55, -0.55))):
        arm = prim(f"{root_name}_Arm_{i}", "cube", (x * 0.55, y * 0.55, 0.05), (0.55, 0.08, 0.06), arm_m, empty)
        hub = prim(f"{root_name}_Hub_{i}", "cyl", (x, y, 0.12), (0.12, 0.12, 0.08), arm_m, empty)
        prop = prim(f"{root_name}_Prop_{i}", "cube", (x, y, 0.18), (0.55, 0.06, 0.02), prop_m, empty)
        props.append(prop)
    return empty, props


def export_fbx(path: Path):
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=False,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        object_types={"EMPTY", "MESH"},
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        path_mode="AUTO",
    )


def main():
    clear_scene()
    build_vav_ahu("AHU_VAV_Sys1", "VAV Sys 1")
    # Offset second AHU in Blender scene for visual QA; Unity places both
    ahu2 = build_vav_ahu("AHU_VAV_Sys2", "VAV Sys 2")
    ahu2.location.x = 8.0
    drone, _ = build_drone("TwinDrone")
    drone.location = (0, -6, 1.5)

    export_fbx(OUT / "RoofAhu_VAV.fbx")
    # Export drone alone
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if obj.name.startswith("TwinDrone") or (obj.parent and obj.parent.name.startswith("TwinDrone")):
            obj.select_set(True)
        if obj.name == "TwinDrone":
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=str(OUT / "TwinDrone.fbx"),
        use_selection=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        object_types={"EMPTY", "MESH"},
        add_leaf_bones=False,
    )
    print("Exported", OUT)


if __name__ == "__main__":
    main()
