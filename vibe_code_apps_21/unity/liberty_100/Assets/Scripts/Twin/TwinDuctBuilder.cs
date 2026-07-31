using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Imaginary DEMO duct trunks from roof AHUs down to floor zone sensors.
    /// Not CAD — illustrative distribution paths only.
    /// </summary>
    public class TwinDuctBuilder : MonoBehaviour
    {
        public float ductWidth = 0.55f;
        public Color ductColor = new Color(0.62f, 0.66f, 0.7f, 1f);

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Build Imaginary Ductwork")]
        public static void MenuBuild()
        {
            var go = GameObject.Find("TwinDuctBuilder");
            if (go == null) go = new GameObject("TwinDuctBuilder");
            var b = go.GetComponent<TwinDuctBuilder>() ?? go.AddComponent<TwinDuctBuilder>();
            b.Build();
        }
#endif

        public void Build()
        {
            var existing = GameObject.Find("TwinDemoDucts");
            if (existing != null) DestroyImmediate(existing);
            var root = new GameObject("TwinDemoDucts");

            var ahu1 = FindAhu("ahu_proxy_vav_sys_1");
            var ahu2 = FindAhu("ahu_proxy_vav_sys_2");
            var sensors = FindObjectsByType<ZoneTempSensor>();

            var mat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            mat.color = ductColor;
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", ductColor);

            // Vertical shafts near building core
            Vector3 shaft1 = new Vector3(12f, 0f, 19f);
            Vector3 shaft2 = new Vector3(44f, 0f, 19f);
            float roofY = 24f;
            if (ahu1 != null) { shaft1.x = ahu1.position.x; shaft1.z = ahu1.position.z; roofY = Mathf.Max(roofY, ahu1.position.y); }
            if (ahu2 != null) { shaft2.x = ahu2.position.x; shaft2.z = ahu2.position.z; roofY = Mathf.Max(roofY, ahu2.position.y); }

            MakeSegment(root.transform, "Shaft_AHU1", new Vector3(shaft1.x, 1f, shaft1.z), new Vector3(shaft1.x, roofY, shaft1.z), mat);
            MakeSegment(root.transform, "Shaft_AHU2", new Vector3(shaft2.x, 1f, shaft2.z), new Vector3(shaft2.x, roofY, shaft2.z), mat);

            // Roof laterals AHU → shaft top
            if (ahu1 != null)
                MakeSegment(root.transform, "RoofLat_AHU1", ahu1.position, new Vector3(shaft1.x, roofY, shaft1.z), mat);
            if (ahu2 != null)
                MakeSegment(root.transform, "RoofLat_AHU2", ahu2.position, new Vector3(shaft2.x, roofY, shaft2.z), mat);

            int branches = 0;
            foreach (var s in sensors)
            {
                if (s == null) continue;
                bool ahu2Side = (s.zoneEntityId != null && s.zoneEntityId.Contains("ahu2"))
                    || (s.floorLabel != null && s.floorLabel.Contains("AHU-2"));
                var shaft = ahu2Side ? shaft2 : shaft1;
                var sp = s.transform.position;
                var junction = new Vector3(shaft.x, sp.y, shaft.z);
                MakeSegment(root.transform, $"Branch_{s.zoneEntityId}_h", junction, sp, mat);
                branches++;
            }

            var te = root.AddComponent<TwinEntity>();
            te.entityId = "duct_demo_network";
            te.entityType = "duct_proxy";
            te.displayName = "DEMO imaginary ductwork";
            te.isDemoProxy = true;
            Debug.Log($"TwinDuctBuilder: shafts + {branches} zone branches (DEMO)");
        }

        static Transform FindAhu(string entityId)
        {
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType == "ahu_proxy" && te.entityId == entityId)
                    return te.transform;
            }
            return null;
        }

        void MakeSegment(Transform parent, string name, Vector3 a, Vector3 b, Material mat)
        {
            var mid = (a + b) * 0.5f;
            var len = Vector3.Distance(a, b);
            if (len < 0.05f) return;
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.position = mid;
            go.transform.localScale = new Vector3(ductWidth, ductWidth, len);
            go.transform.rotation = Quaternion.LookRotation((b - a).normalized, Vector3.up);
            var col = go.GetComponent<Collider>();
            if (col != null) DestroyImmediate(col);
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
        }
    }
}
