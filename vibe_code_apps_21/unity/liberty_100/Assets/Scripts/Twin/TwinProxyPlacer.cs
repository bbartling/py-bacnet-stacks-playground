using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// DEMO zone temp sensors near exterior windows + optional legacy AHU boxes.
    /// One bulb + one short label per zone (no stacked DEMO spam).
    /// </summary>
    public class TwinProxyPlacer : MonoBehaviour
    {
        public void PlaceProxies()
        {
            var existing = GameObject.Find("TwinDemoProxies");
            if (existing != null) DestroyImmediate(existing);
            var root = new GameObject("TwinDemoProxies");

            var zones = new List<TwinEntity>();
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType == "zone") zones.Add(te);
            }

            // Sort for stable stagger index
            zones.Sort((a, b) => string.CompareOrdinal(a.displayName, b.displayName));

            int idx = 0;
            foreach (var z in zones)
            {
                int floor = 1;
                var m = Regex.Match(z.displayName ?? "", @"Floor_(\d+)");
                if (m.Success) floor = int.Parse(m.Groups[1].Value);
                bool ahu2 = (z.displayName ?? "").Contains("AHU2");
                string ahu = ahu2 ? "AHU2" : "AHU1";

                var pos = WindowMidpointForZone(z.entityId);
                if (!pos.HasValue)
                {
                    var bounds = GetHierarchyBounds(z.transform);
                    pos = new Vector3(bounds.center.x, Mathf.Lerp(bounds.min.y, bounds.max.y, 0.55f), bounds.center.z);
                }

                // Slight vertical stagger by floor×AHU so labels never share a pixel
                float stagger = ((floor - 1) * 2 + (ahu2 ? 1 : 0)) * 0.12f + (idx % 3) * 0.05f;
                var sensorPos = pos.Value + Vector3.up * (0.35f + stagger);

                var sensor = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                sensor.name = $"TempProxy_{z.entityId}";
                sensor.transform.SetParent(root.transform, false);
                sensor.transform.position = sensorPos;
                sensor.transform.localScale = Vector3.one * 0.4f;
                var sm = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                sm.color = new Color(0.75f, 0.78f, 0.82f);
                var bulb = sensor.GetComponent<MeshRenderer>();
                bulb.sharedMaterial = sm;
                var ste = sensor.AddComponent<TwinEntity>();
                ste.entityId = z.entityId + "_temp_proxy";
                ste.entityType = "sensor_proxy";
                ste.displayName = $"F{floor} {ahu} sensor";
                ste.isDemoProxy = true;

                var labelGo = new GameObject("Label");
                labelGo.transform.SetParent(sensor.transform, false);
                labelGo.transform.localPosition = new Vector3(0f, 0.75f, 0f);
                var tm = labelGo.AddComponent<TextMesh>();
                tm.characterSize = 0.09f;
                tm.fontSize = 40;
                tm.anchor = TextAnchor.MiddleCenter;
                tm.alignment = TextAlignment.Center;
                tm.color = new Color(0.95f, 0.95f, 0.95f);

                var zts = sensor.AddComponent<ZoneTempSensor>();
                zts.zoneEntityId = z.entityId;
                zts.floorLabel = $"F{floor} {ahu}";
                zts.label = tm;
                zts.bulb = bulb;
                zts.SetTemp(22.5f);
                idx++;
            }

            // Do not place opaque AHU cubes when x-ray roof AHUs exist
            bool hasRoofAhu = false;
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType == "ahu_proxy") { hasRoofAhu = true; break; }
            }
            if (!hasRoofAhu)
            {
                foreach (var z in zones)
                {
                    if (z.displayName == null || !z.displayName.StartsWith("Floor_6_AHU")) continue;
                    var bounds = GetHierarchyBounds(z.transform);
                    var apos = new Vector3(bounds.center.x, bounds.max.y + 1.2f, bounds.center.z);
                    var ahu = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    ahu.name = $"AHU_Proxy_{z.entityId}";
                    ahu.transform.SetParent(root.transform, false);
                    ahu.transform.position = apos;
                    ahu.transform.localScale = new Vector3(4f, 1.4f, 2.5f);
                    var am = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                    am.color = new Color(0.55f, 0.55f, 0.6f);
                    ahu.GetComponent<MeshRenderer>().sharedMaterial = am;
                    var ate = ahu.AddComponent<TwinEntity>();
                    ate.entityId = z.entityId.Replace("zone_", "ahu_proxy_");
                    ate.entityType = "ahu_proxy";
                    ate.displayName = "DEMO roof AHU proxy";
                    ate.isDemoProxy = true;
                }
            }
            Debug.Log($"TwinProxyPlacer: {zones.Count} window-side temp sensors (short labels)");
        }

        static Vector3? WindowMidpointForZone(string zoneEntityId)
        {
            if (string.IsNullOrEmpty(zoneEntityId)) return null;
            Bounds? b = null;
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "window") continue;
                if (te.entityId != zoneEntityId) continue;
                foreach (var r in te.GetComponentsInChildren<Renderer>())
                {
                    if (b == null) b = r.bounds;
                    else
                    {
                        var bb = b.Value;
                        bb.Encapsulate(r.bounds);
                        b = bb;
                    }
                }
            }
            return b?.center;
        }

        static Bounds GetHierarchyBounds(Transform t)
        {
            var renderers = t.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0) return new Bounds(t.position, Vector3.one * 2f);
            var b = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) b.Encapsulate(renderers[i].bounds);
            return b;
        }

#if UNITY_EDITOR
        [UnityEditor.MenuItem("Vibe21/Twin/Place DEMO Proxies")]
        public static void MenuPlace()
        {
            var go = GameObject.Find("TwinProxyPlacer");
            if (go == null) go = new GameObject("TwinProxyPlacer");
            var p = go.GetComponent<TwinProxyPlacer>() ?? go.AddComponent<TwinProxyPlacer>();
            p.PlaceProxies();
        }
#endif
    }
}
