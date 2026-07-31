using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Places Blender VAV AHU FBX on roof + cartoon drone follow-cam.
    /// IDF: AirLoopHVAC "VAV Sys 1/2" + Fan:VariableVolume + CHW coils.
    /// </summary>
    public class RoofAssetPlacer : MonoBehaviour
    {
        public GameObject ahuFbx;
        public GameObject droneFbx;

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
                ahuFbx = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/Twin/RoofAhu_VAV.fbx");
            if (droneFbx == null)
                droneFbx = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/Twin/TwinDrone.fbx");
#endif
            var existing = GameObject.Find("TwinBlenderRoof");
            if (existing != null) DestroyImmediate(existing);
            var root = new GameObject("TwinBlenderRoof");

            // Hide old cube AHU proxies
            var proxies = GameObject.Find("TwinDemoProxies");
            if (proxies != null)
            {
                foreach (Transform c in proxies.transform)
                {
                    if (c.name.StartsWith("AHU_Proxy_"))
                        c.gameObject.SetActive(false);
                }
            }

            PlaceOneAhu(root.transform, "AHU_VAV_Sys1", "ahu_proxy_vav_sys_1", "VAV Sys 1",
                FindRoofAnchor("Floor_6_AHU1"), new Vector3(-1.5f, 0f, 0f));
            PlaceOneAhu(root.transform, "AHU_VAV_Sys2", "ahu_proxy_vav_sys_2", "VAV Sys 2",
                FindRoofAnchor("Floor_6_AHU2"), new Vector3(1.5f, 0f, 0f));

            if (droneFbx != null)
            {
                var drone = Instantiate(droneFbx);
                drone.name = "TwinDroneVisual";
                drone.transform.SetParent(root.transform, false);
                var bob = drone.AddComponent<DroneVisualBob>();
                bob.follow = Camera.main != null ? Camera.main.transform : null;
                var props = new System.Collections.Generic.List<Transform>();
                foreach (var t in drone.GetComponentsInChildren<Transform>())
                {
                    if (t.name.Contains("Prop")) props.Add(t);
                }
                bob.props = props.ToArray();
                var te = drone.AddComponent<TwinEntity>();
                te.entityId = "drone_visual_demo";
                te.entityType = "drone_proxy";
                te.displayName = "DEMO cartoon drone";
                te.isDemoProxy = true;
            }

            Debug.Log("RoofAssetPlacer: VAV Sys 1/2 AHUs + drone (Blender FBX / DEMO)");
        }

        void PlaceOneAhu(Transform parent, string name, string entityId, string airLoop, Bounds roof, Vector3 nudge)
        {
            GameObject inst;
            if (ahuFbx != null)
            {
                inst = Instantiate(ahuFbx);
            }
            else
            {
                inst = GameObject.CreatePrimitive(PrimitiveType.Cube);
                inst.transform.localScale = new Vector3(4.2f, 1.4f, 2.4f);
            }
            inst.name = name;
            inst.transform.SetParent(parent, false);
            var pos = roof.center + Vector3.up * (roof.extents.y + 1.1f) + nudge;
            inst.transform.position = pos;
            inst.transform.localScale = Vector3.one * 1.0f;

            var te = inst.AddComponent<TwinEntity>();
            te.entityId = entityId;
            te.entityType = "ahu_proxy";
            te.displayName = $"{airLoop} (VAV_CHW DEMO)";
            te.isDemoProxy = true;

            var spin = inst.AddComponent<AhuFanSpin>();
            spin.airLoopName = airLoop;
            spin.ahuType = "VAV_CHW";
            foreach (var t in inst.GetComponentsInChildren<Transform>())
            {
                if (t.name.Contains("FanWheel"))
                {
                    spin.fanWheel = t;
                    break;
                }
            }
            if (spin.fanWheel == null)
            {
                // Fallback: spin whole cabinet slightly silly
                spin.fanWheel = inst.transform;
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
