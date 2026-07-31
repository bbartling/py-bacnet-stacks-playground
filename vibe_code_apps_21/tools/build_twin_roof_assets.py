# Build ONE VAV AHU + ONE coherent drone for Unity.
# Exports:
#   RoofAhu_VAV_Single.fbx  — instantiate twice in Unity
#   TwinDrone.fbx           — flyable vehicle with Prop_* under Rotor_* hubs

import bpy
import math
from pathlib import Path

OUT = Path(r"C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_21\unity\liberty_100\Assets\Models\Twin")
OUT.mkdir(parents=True, exist_ok=True)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials):
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


def mesh(name, typ, loc, scale, material, parent=None):
    """Create mesh as child; loc/scale are LOCAL to parent when parent set."""
    if typ == "cube":
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    elif typ == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1, location=(0, 0, 0))
    elif typ == "uv":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 0))
    else:
        raise ValueError(typ)
    obj = bpy.context.active_object
    obj.name = name
    if parent is not None:
        obj.parent = parent
        obj.location = loc
        obj.scale = scale
    else:
        obj.location = loc
        obj.scale = scale
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.empty_display_size = 0.2
    if parent is not None:
        e.parent = parent
        e.location = loc
    else:
        e.location = loc
    return e


def build_single_ahu(root_name="AHU_VAV"):
    root = empty(root_name)
    root["ahu_type"] = "VAV_CHW"
    steel = mat(f"{root_name}_steel", (0.55, 0.58, 0.62, 1), 0.55, 0.35)
    accent = mat(f"{root_name}_accent", (0.15, 0.35, 0.55, 1), 0.2, 0.5)
    fan_m = mat(f"{root_name}_fan", (0.18, 0.18, 0.2, 1), 0.6, 0.3)
    warn = mat(f"{root_name}_warn", (0.85, 0.55, 0.1, 1), 0.1, 0.5)

    mesh(f"{root_name}_Cabinet", "cube", (0, 0, 0.7), (4.2, 2.4, 1.4), steel, root)
    mesh(f"{root_name}_OAHood", "cube", (-1.6, 0, 1.55), (1.2, 1.6, 0.35), accent, root)
    mesh(f"{root_name}_FilterDoor", "cube", (0.2, 1.22, 0.7), (1.6, 0.08, 0.9), warn, root)
    mesh(f"{root_name}_CoilSection", "cube", (1.3, 0, 0.7), (1.0, 2.2, 1.2), accent, root)
    mesh(f"{root_name}_Discharge", "cube", (2.4, 0, 0.55), (0.7, 1.4, 0.9), steel, root)

    fan = mesh(f"{root_name}_FanWheel", "cyl", (0.9, 0, 0.75), (1.0, 1.0, 0.22), fan_m, root)
    fan.rotation_euler = (math.radians(90), 0, 0)
    for i in range(6):
        ang = i * (math.pi / 3)
        blade = mesh(
            f"{root_name}_Blade_{i}",
            "cube",
            (0.35 * math.cos(ang), 0.02, 0.35 * math.sin(ang)),
            (0.5, 0.06, 0.1),
            fan_m,
            fan,
        )
    mesh(f"{root_name}_ReliefCowl", "cyl", (-0.4, -0.9, 1.7), (0.7, 0.7, 0.5), steel, root)
    return root


def build_drone(root_name="TwinDrone"):
    """Coherent quadcopter: body + 4 arms + rotor hubs; props are children of hubs (spin local Z)."""
    root = empty(root_name)
    body_m = mat(f"{root_name}_body", (0.12, 0.55, 0.35, 1), 0.15, 0.4)
    arm_m = mat(f"{root_name}_arm", (0.22, 0.22, 0.25, 1), 0.4, 0.4)
    prop_m = mat(f"{root_name}_prop", (0.95, 0.85, 0.15, 1), 0.05, 0.35)
    lens_m = mat(f"{root_name}_lens", (0.05, 0.05, 0.08, 1), 0.8, 0.15)

    # Body centered at origin
    mesh(f"{root_name}_Body", "uv", (0, 0, 0), (0.7, 0.45, 0.28), body_m, root)
    mesh(f"{root_name}_Cam", "uv", (0.28, 0, -0.12), (0.14, 0.14, 0.14), lens_m, root)

    # Arm reach to motor centers
    reach = 0.62
    corners = (
        (reach, reach),
        (reach, -reach),
        (-reach, reach),
        (-reach, -reach),
    )
    for i, (x, y) in enumerate(corners):
        # Arm from body toward motor
        mid = (x * 0.5, y * 0.5, 0.02)
        arm = mesh(f"{root_name}_Arm_{i}", "cube", mid, (abs(x) * 0.95, 0.07, 0.05), arm_m, root)
        # Point arm along diagonal
        arm.rotation_euler = (0, 0, math.atan2(y, x))

        rotor = empty(f"{root_name}_Rotor_{i}", loc=(x, y, 0.08), parent=root)
        mesh(f"{root_name}_Hub_{i}", "cyl", (0, 0, 0), (0.1, 0.1, 0.06), arm_m, rotor)
        # Flat prop in XY — Unity spins Rotor around local +Y (Blender Z-up → Unity Y-up after FBX)
        # In Blender Z is up: prop is thin in Z, extends in X
        prop = mesh(f"{root_name}_Prop_{i}", "cube", (0, 0, 0.04), (0.55, 0.07, 0.02), prop_m, rotor)
        # Second blade crossed
        prop2 = mesh(f"{root_name}_PropB_{i}", "cube", (0, 0, 0.04), (0.07, 0.55, 0.02), prop_m, rotor)

    return root


def export_selected(path: Path, roots):
    bpy.ops.object.select_all(action="DESELECT")
    for r in roots:
        r.select_set(True)
        for c in r.children_recursive:
            c.select_set(True)
        bpy.context.view_layer.objects.active = r
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        object_types={"EMPTY", "MESH"},
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        bake_space_transform=True,
    )


def main():
    clear_scene()
    ahu = build_single_ahu("AHU_VAV")
    export_selected(OUT / "RoofAhu_VAV_Single.fbx", [ahu])

    clear_scene()
    drone = build_drone("TwinDrone")
    export_selected(OUT / "TwinDrone.fbx", [drone])

    # Keep both in scene for Blender QA
    clear_scene()
    ahu = build_single_ahu("AHU_VAV")
    drone = build_drone("TwinDrone")
    drone.location = (0, -4, 1)
    print("Exported single AHU + fitted drone to", OUT)


if __name__ == "__main__":
    main()
