using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// DEMO proxy markers: zone temp sensors (labeled) + roof AHU boxes. Not CAD / not live BAS.
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

            foreach (var z in zones)
            {
                var bounds = GetHierarchyBounds(z.transform);
                var mid = bounds.center;
                // Sit sensors near exterior so drone can read them through windows
                mid.y = Mathf.Lerp(bounds.min.y, bounds.max.y, 0.55f);
                var sensor = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                sensor.name = $"TempProxy_{z.entityId}";
                sensor.transform.SetParent(root.transform, false);
                sensor.transform.position = mid;
                sensor.transform.localScale = Vector3.one * 0.55f;
                var sm = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                sm.color = new Color(0.2f, 0.85f, 0.95f);
                sm.EnableKeyword("_EMISSION");
                if (sm.HasProperty("_EmissionColor"))
                    sm.SetColor("_EmissionColor", new Color(0.15f, 0.4f, 0.5f));
                var bulb = sensor.GetComponent<MeshRenderer>();
                bulb.sharedMaterial = sm;
                var ste = sensor.AddComponent<TwinEntity>();
                ste.entityId = z.entityId + "_temp_proxy";
                ste.entityType = "sensor_proxy";
                ste.displayName = "DEMO zone temp proxy";
                ste.isDemoProxy = true;

                var labelGo = new GameObject("Label");
                labelGo.transform.SetParent(sensor.transform, false);
                labelGo.transform.localPosition = new Vector3(0f, 0.9f, 0f);
                var tm = labelGo.AddComponent<TextMesh>();
                tm.characterSize = 0.12f;
                tm.fontSize = 48;
                tm.anchor = TextAnchor.MiddleCenter;
                tm.alignment = TextAlignment.Center;
                tm.color = Color.white;
                int floor = 1;
                var m = Regex.Match(z.displayName ?? "", @"Floor_(\d+)");
                if (m.Success) floor = int.Parse(m.Groups[1].Value);
                string ahu = (z.displayName ?? "").Contains("AHU2") ? "AHU-2" : "AHU-1";

                var zts = sensor.AddComponent<ZoneTempSensor>();
                zts.zoneEntityId = z.entityId;
                zts.floorLabel = $"F{floor} {ahu}";
                zts.label = tm;
                zts.bulb = bulb;
                zts.SetTemp(22.5f);
            }

            foreach (var z in zones)
            {
                if (z.displayName == null || !z.displayName.StartsWith("Floor_6_AHU")) continue;
                var bounds = GetHierarchyBounds(z.transform);
                var pos = new Vector3(bounds.center.x, bounds.max.y + 1.2f, bounds.center.z);
                var ahu = GameObject.CreatePrimitive(PrimitiveType.Cube);
                ahu.name = $"AHU_Proxy_{z.entityId}";
                ahu.transform.SetParent(root.transform, false);
                ahu.transform.position = pos;
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
            Debug.Log($"TwinProxyPlacer: {zones.Count} labeled temp proxies + roof AHUs (DEMO)");
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
