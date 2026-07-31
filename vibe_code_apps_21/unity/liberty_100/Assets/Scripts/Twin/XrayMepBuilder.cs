using System.Collections.Generic;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// X-ray DEMO MEP: blue supply + orange return risers, floor laterals,
    /// thin CHW/HW pipes. Illustrative — not CAD.
    /// </summary>
    public class XrayMepBuilder : MonoBehaviour
    {
        public float ductW = 0.65f;
        public float pipeW = 0.18f;

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Build X-Ray MEP")]
        public static void MenuBuild()
        {
            var go = GameObject.Find("XrayMepBuilder") ?? new GameObject("XrayMepBuilder");
            var b = go.GetComponent<XrayMepBuilder>() ?? go.AddComponent<XrayMepBuilder>();
            b.Build();
        }
#endif

        public void Build()
        {
            var old = GameObject.Find("TwinDemoDucts");
            if (old != null) DestroyImmediate(old);
            var old2 = GameObject.Find("TwinXrayMep");
            if (old2 != null) DestroyImmediate(old2);

            var root = new GameObject("TwinXrayMep");
            var supplyMat = Trans(new Color(0.25f, 0.45f, 0.9f, 0.45f));
            var returnMat = Trans(new Color(0.9f, 0.45f, 0.25f, 0.45f));
            var chwMat = Trans(new Color(0.2f, 0.55f, 0.95f, 0.55f));
            var hwMat = Trans(new Color(0.95f, 0.35f, 0.25f, 0.55f));

            var ahu1 = FindAhu("ahu_proxy_vav_sys_1");
            var ahu2 = FindAhu("ahu_proxy_vav_sys_2");

            Vector3 s1 = ahu1 != null ? ahu1.position : new Vector3(12f, 25f, 19f);
            Vector3 s2 = ahu2 != null ? ahu2.position : new Vector3(45f, 25f, 19f);
            float roofY = Mathf.Max(s1.y, s2.y);
            float groundY = 1.2f;

            // Supply risers (slightly offset from return)
            Vector3 supplyShaft1 = new Vector3(s1.x - 1.2f, 0f, s1.z + 1.5f);
            Vector3 supplyShaft2 = new Vector3(s2.x + 1.2f, 0f, s2.z + 1.5f);
            Vector3 returnShaft1 = new Vector3(s1.x + 1.0f, 0f, s1.z - 1.2f);
            Vector3 returnShaft2 = new Vector3(s2.x - 1.0f, 0f, s2.z - 1.2f);

            Seg(root.transform, "SupplyRiser_AHU1", new Vector3(supplyShaft1.x, groundY, supplyShaft1.z), new Vector3(supplyShaft1.x, roofY, supplyShaft1.z), ductW, supplyMat);
            Seg(root.transform, "SupplyRiser_AHU2", new Vector3(supplyShaft2.x, groundY, supplyShaft2.z), new Vector3(supplyShaft2.x, roofY, supplyShaft2.z), ductW, supplyMat);
            Seg(root.transform, "ReturnRiser_AHU1", new Vector3(returnShaft1.x, groundY, returnShaft1.z), new Vector3(returnShaft1.x, roofY, returnShaft1.z), ductW * 0.9f, returnMat);
            Seg(root.transform, "ReturnRiser_AHU2", new Vector3(returnShaft2.x, groundY, returnShaft2.z), new Vector3(returnShaft2.x, roofY, returnShaft2.z), ductW * 0.9f, returnMat);

            // Roof laterals AHU ↔ risers
            Seg(root.transform, "RoofSupply_1", s1 + Vector3.right * 1.5f, new Vector3(supplyShaft1.x, roofY, supplyShaft1.z), ductW * 0.7f, supplyMat);
            Seg(root.transform, "RoofSupply_2", s2 + Vector3.left * 1.5f, new Vector3(supplyShaft2.x, roofY, supplyShaft2.z), ductW * 0.7f, supplyMat);
            Seg(root.transform, "RoofReturn_1", s1 + new Vector3(0.5f, -0.8f, -1f), new Vector3(returnShaft1.x, roofY - 0.5f, returnShaft1.z), ductW * 0.65f, returnMat);
            Seg(root.transform, "RoofReturn_2", s2 + new Vector3(-0.5f, -0.8f, -1f), new Vector3(returnShaft2.x, roofY - 0.5f, returnShaft2.z), ductW * 0.65f, returnMat);

            // CHW / HW pipe risers (DEMO plant feed)
            Vector3 pipe1 = new Vector3(28f, 0f, 8f);
            Vector3 pipe2 = new Vector3(28f, 0f, 10f);
            Seg(root.transform, "CHW_Riser", new Vector3(pipe1.x, groundY, pipe1.z), new Vector3(pipe1.x, roofY, pipe1.z), pipeW, chwMat);
            Seg(root.transform, "HW_Riser", new Vector3(pipe2.x, groundY, pipe2.z), new Vector3(pipe2.x, roofY, pipe2.z), pipeW, hwMat);
            Seg(root.transform, "CHW_to_AHU1", new Vector3(pipe1.x, roofY - 0.3f, pipe1.z), s1 + Vector3.down * 0.5f, pipeW * 0.85f, chwMat);
            Seg(root.transform, "CHW_to_AHU2", new Vector3(pipe1.x, roofY - 0.3f, pipe1.z), s2 + Vector3.down * 0.5f, pipeW * 0.85f, chwMat);
            Seg(root.transform, "HW_to_AHU1", new Vector3(pipe2.x, roofY - 0.5f, pipe2.z), s1 + Vector3.down * 0.7f, pipeW * 0.85f, hwMat);
            Seg(root.transform, "HW_to_AHU2", new Vector3(pipe2.x, roofY - 0.5f, pipe2.z), s2 + Vector3.down * 0.7f, pipeW * 0.85f, hwMat);

            // Floor laterals + diffuser proxies from zone sensors / zones
            int n = 0;
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone") continue;
                bool isAhu2 = te.displayName != null && te.displayName.Contains("AHU2");
                var shaftS = isAhu2 ? supplyShaft2 : supplyShaft1;
                var shaftR = isAhu2 ? returnShaft2 : returnShaft1;
                var b = BoundsOf(te.transform);
                var center = b.center;
                float y = center.y;
                var jS = new Vector3(shaftS.x, y, shaftS.z);
                var jR = new Vector3(shaftR.x, y + 0.35f, shaftR.z);
                Seg(root.transform, $"SupplyLat_{te.entityId}", jS, center + Vector3.up * 0.8f, ductW * 0.35f, supplyMat);
                Seg(root.transform, $"ReturnLat_{te.entityId}", center + Vector3.up * 1.1f, jR, ductW * 0.32f, returnMat);

                // Diffuser proxy
                var diff = GameObject.CreatePrimitive(PrimitiveType.Cube);
                diff.name = $"Diffuser_{te.entityId}";
                diff.transform.SetParent(root.transform, false);
                diff.transform.position = center + Vector3.up * (b.extents.y * 0.85f);
                diff.transform.localScale = new Vector3(0.7f, 0.08f, 0.7f);
                diff.GetComponent<MeshRenderer>().sharedMaterial = supplyMat;
                KillCol(diff);
                n++;
            }

            var meta = root.AddComponent<TwinEntity>();
            meta.entityId = "mep_xray_demo";
            meta.entityType = "duct_proxy";
            meta.displayName = "DEMO x-ray ducts/pipes";
            meta.isDemoProxy = true;
            Debug.Log($"XrayMepBuilder: supply/return risers + {n} floor branches + CHW/HW (DEMO)");
        }

        static Transform FindAhu(string entityId)
        {
            foreach (var te in FindObjectsByType<TwinEntity>())
                if (te.entityType == "ahu_proxy" && te.entityId == entityId)
                    return te.transform;
            return null;
        }

        static Bounds BoundsOf(Transform t)
        {
            var rs = t.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return new Bounds(t.position, Vector3.one * 4f);
            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            return b;
        }

        static void Seg(Transform parent, string name, Vector3 a, Vector3 b, float width, Material mat)
        {
            float len = Vector3.Distance(a, b);
            if (len < 0.08f) return;
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.position = (a + b) * 0.5f;
            go.transform.localScale = new Vector3(width, width, len);
            go.transform.rotation = Quaternion.LookRotation((b - a).normalized, Vector3.up);
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
            KillCol(go);
        }

        static void KillCol(GameObject go)
        {
            var c = go.GetComponent<Collider>();
            if (c == null) return;
            if (Application.isPlaying) Object.Destroy(c);
            else Object.DestroyImmediate(c);
        }

        static Material Trans(Color c)
        {
            var m = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            m.color = c;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            if (m.HasProperty("_Surface")) m.SetFloat("_Surface", 1f);
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.renderQueue = 3000;
            return m;
        }
    }
}
