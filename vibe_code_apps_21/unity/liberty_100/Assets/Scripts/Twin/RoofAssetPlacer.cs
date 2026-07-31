using System.Collections.Generic;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Places exactly two VAV AHUs on the roof + one flyable drone (WASD).
    /// Uses single-AHU FBX (not the dual-packed export).
    /// </summary>
    public class RoofAssetPlacer : MonoBehaviour
    {
        public GameObject ahuFbx;
        public GameObject droneFbx;
        public Vector3 droneSpawn = new Vector3(40f, 30f, -35f);

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Place Blender Roof AHUs + Drone")]
        public static void MenuPlace()
        {
            var go = GameObject.Find("RoofAssetPlacer");
            if (go == null) go = new GameObject("RoofAssetPlacer");
            var p = go.GetComponent<RoofAssetPlacer>() ?? go.AddComponent<RoofAssetPlacer>();
            p.Place();
        }
#endif

        public void Place()
        {
#if UNITY_EDITOR
            if (ahuFbx == null)
            {
                ahuFbx = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/Twin/RoofAhu_VAV_Single.fbx");
                if (ahuFbx == null)
                    ahuFbx = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/Twin/RoofAhu_VAV.fbx");
            }
            if (droneFbx == null)
                droneFbx = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/Twin/TwinDrone.fbx");
#endif
            // Tear down prior blender roof + any stray AHU proxies
            var existing = GameObject.Find("TwinBlenderRoof");
            if (existing != null) DestroyImmediate(existing);

            var proxies = GameObject.Find("TwinDemoProxies");
            if (proxies != null)
            {
                var toKill = new List<GameObject>();
                for (int i = 0; i < proxies.transform.childCount; i++)
                {
                    var c = proxies.transform.GetChild(i);
                    if (c != null && (c.name.StartsWith("AHU_Proxy_") || c.name.Contains("AHU_VAV")))
                        toKill.Add(c.gameObject);
                }
                foreach (var g in toKill)
                {
                    if (g != null) DestroyImmediate(g);
                }
            }

            // Remove leftover drone/ahu not under TwinBlenderRoof
            var strays = new List<GameObject>();
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te == null) continue;
                if (te.entityType != "ahu_proxy" && te.entityType != "drone_proxy") continue;
                strays.Add(te.gameObject);
            }
            foreach (var g in strays)
            {
                if (g != null) DestroyImmediate(g);
            }

            var root = new GameObject("TwinBlenderRoof");

            PlaceOneAhu(root.transform, "AHU_VAV_Sys1", "ahu_proxy_vav_sys_1", "VAV Sys 1",
                FindRoofAnchor("Floor_6_AHU1"), new Vector3(-2.5f, 0f, 0f));
            PlaceOneAhu(root.transform, "AHU_VAV_Sys2", "ahu_proxy_vav_sys_2", "VAV Sys 2",
                FindRoofAnchor("Floor_6_AHU2"), new Vector3(2.5f, 0f, 0f));

            EnforceExactlyTwoAhus(root.transform);

            SpawnFlyableDrone(root.transform);
            Debug.Log("RoofAssetPlacer: exactly 2 VAV AHUs + flyable TwinDrone (WASD)");
        }

        void EnforceExactlyTwoAhus(Transform root)
        {
            if (root == null) return;
            // Collect top-level AHU children safely first
            var ahus = new List<Transform>();
            for (int i = 0; i < root.childCount; i++)
            {
                var c = root.GetChild(i);
                if (c != null && c.name.StartsWith("AHU_"))
                    ahus.Add(c);
            }
            // Destroy extras beyond 2
            for (int i = 2; i < ahus.Count; i++)
            {
                if (ahus[i] != null)
                    DestroyImmediate(ahus[i].gameObject);
            }
        }

        void SpawnFlyableDrone(Transform parent)
        {
            GameObject drone;
            if (droneFbx != null)
                drone = Instantiate(droneFbx);
            else
            {
                drone = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                drone.transform.localScale = new Vector3(0.8f, 0.35f, 0.5f);
            }
            drone.name = "TwinDrone";
            drone.transform.SetParent(parent, false);
            drone.transform.position = droneSpawn;
            drone.transform.rotation = Quaternion.Euler(0f, 180f, 0f);

            // Remove old follow-bob if present
            var bob = drone.GetComponent<DroneVisualBob>();
            if (bob != null) DestroyImmediate(bob);

            var ctrl = drone.GetComponent<DroneController>() ?? drone.AddComponent<DroneController>();
            ctrl.cameraRig = Camera.main != null ? Camera.main.transform : null;
            var rotors = new List<Transform>();
            foreach (var t in drone.GetComponentsInChildren<Transform>())
            {
                if (t.name.Contains("Rotor_"))
                    rotors.Add(t);
            }
            // Fallback: prop meshes themselves
            if (rotors.Count == 0)
            {
                foreach (var t in drone.GetComponentsInChildren<Transform>())
                {
                    if (t.name.Contains("Prop") && !t.name.Contains("PropB"))
                        rotors.Add(t);
                }
            }
            ctrl.rotors = rotors.ToArray();

            var te = drone.GetComponent<TwinEntity>() ?? drone.AddComponent<TwinEntity>();
            te.entityId = "drone_player";
            te.entityType = "drone_proxy";
            te.displayName = "Flyable DEMO drone";
            te.isDemoProxy = true;

            // Disable freefly on main camera
            if (Camera.main != null)
            {
                var ff = Camera.main.GetComponent<DroneFlyCamera>();
                if (ff != null) ff.enabled = false;
            }
        }

        void PlaceOneAhu(Transform parent, string name, string entityId, string airLoop, Bounds roof, Vector3 nudge)
        {
            GameObject inst;
            if (ahuFbx != null)
                inst = Instantiate(ahuFbx);
            else
            {
                inst = GameObject.CreatePrimitive(PrimitiveType.Cube);
                inst.transform.localScale = new Vector3(4.2f, 1.4f, 2.4f);
            }
            inst.name = name;
            inst.transform.SetParent(parent, false);
            var pos = new Vector3(roof.center.x, roof.max.y + 1.15f, roof.center.z) + nudge;
            inst.transform.position = pos;

            // If this FBX still has two AHU roots, keep only the first mesh group
            StripDualAhuChildren(inst.transform);

            var te = inst.GetComponent<TwinEntity>() ?? inst.AddComponent<TwinEntity>();
            te.entityId = entityId;
            te.entityType = "ahu_proxy";
            te.displayName = $"{airLoop} (VAV_CHW DEMO)";
            te.isDemoProxy = true;

            var spin = inst.GetComponent<AhuFanSpin>() ?? inst.AddComponent<AhuFanSpin>();
            spin.airLoopName = airLoop;
            spin.ahuType = "VAV_CHW";
            spin.fanWheel = null;
            foreach (var t in inst.GetComponentsInChildren<Transform>())
            {
                if (t.name.Contains("FanWheel"))
                {
                    spin.fanWheel = t;
                    break;
                }
            }

            // Leave / mix / return DEMO readout above cabinet
            var labelGo = new GameObject("AirTempLabel");
            labelGo.transform.SetParent(inst.transform, false);
            labelGo.transform.localPosition = new Vector3(0f, 2.4f, 0f);
            var tm = labelGo.AddComponent<TextMesh>();
            tm.characterSize = 0.14f;
            tm.fontSize = 48;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = new Color(0.95f, 0.95f, 0.7f);
            var air = inst.GetComponent<AhuAirTempDisplay>() ?? inst.AddComponent<AhuAirTempDisplay>();
            air.airLoopName = airLoop;
            air.isAhu2 = airLoop.Contains("2");
            air.label = tm;
            air.RefreshLabel();
        }

        static void StripDualAhuChildren(Transform root)
        {
            // Old RoofAhu_VAV.fbx had AHU_VAV_Sys1 + AHU_VAV_Sys2 as siblings under import root
            var kill = new List<GameObject>();
            foreach (Transform c in root)
            {
                if (c.name.Contains("Sys2") || c.name.Contains("TwinDrone"))
                    kill.Add(c.gameObject);
            }
            // Also search one level deeper (FBX wrapper)
            foreach (Transform c in root.GetComponentsInChildren<Transform>())
            {
                if (c == root) continue;
                if (c.parent != null && c.parent != root && c.parent.parent == root)
                {
                    if (c.name.Contains("AHU_VAV_Sys2") || c.name.StartsWith("TwinDrone"))
                        kill.Add(c.gameObject);
                }
            }
            foreach (var g in kill)
            {
                if (g != null) DestroyImmediate(g);
            }
        }

        static Bounds FindRoofAnchor(string zoneName)
        {
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType == "zone" && te.displayName == zoneName)
                {
                    var rs = te.GetComponentsInChildren<Renderer>();
                    if (rs.Length == 0) return new Bounds(te.transform.position + Vector3.up * 22f, Vector3.one * 8f);
                    var b = rs[0].bounds;
                    for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
                    return b;
                }
            }
            return new Bounds(new Vector3(28f, 22f, 19f), new Vector3(20f, 2f, 20f));
        }
    }
}
