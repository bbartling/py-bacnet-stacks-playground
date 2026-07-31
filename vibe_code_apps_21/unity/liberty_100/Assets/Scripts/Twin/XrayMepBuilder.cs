using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Fat x-ray MEP: supply/return ducts + CHW/CW plant pipes (no HW to AHUs).
    /// Builds chiller + cooling tower via XrayPlantFactory.
    /// </summary>
    public class XrayMepBuilder : MonoBehaviour
    {
        public float ductW = 0.95f;
        public float chwPipeW = 0.55f;
        public float cwPipeW = 0.48f;

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
            var supplyMat = Trans(new Color(0.25f, 0.45f, 0.9f, 0.5f));
            var returnMat = Trans(new Color(0.9f, 0.45f, 0.25f, 0.5f));
            var chwMat = Trans(new Color(0.2f, 0.55f, 0.95f, 0.65f));
            var cwMat = Trans(new Color(0.1f, 0.7f, 0.72f, 0.65f));

            var ahu1 = FindAhu("ahu_proxy_vav_sys_1");
            var ahu2 = FindAhu("ahu_proxy_vav_sys_2");

            Vector3 s1 = ahu1 != null ? ahu1.position : new Vector3(12f, 25f, 19f);
            Vector3 s2 = ahu2 != null ? ahu2.position : new Vector3(45f, 25f, 19f);
            float roofY = Mathf.Max(s1.y, s2.y);
            float groundY = 1.2f;

            // Chiller courtyard (south of massing) + tower near roof east
            Vector3 chillerPos = new Vector3(28f, 0.3f, -8f);
            Vector3 towerPos = new Vector3(52f, roofY + 0.5f, 22f);
            XrayPlantFactory.Build(root.transform, chillerPos, towerPos);

            Vector3 supplyShaft1 = new Vector3(s1.x - 1.5f, 0f, s1.z + 2.0f);
            Vector3 supplyShaft2 = new Vector3(s2.x + 1.5f, 0f, s2.z + 2.0f);
            Vector3 returnShaft1 = new Vector3(s1.x + 1.2f, 0f, s1.z - 1.5f);
            Vector3 returnShaft2 = new Vector3(s2.x - 1.2f, 0f, s2.z - 1.5f);

            Seg(root.transform, "SupplyRiser_AHU1", new Vector3(supplyShaft1.x, groundY, supplyShaft1.z), new Vector3(supplyShaft1.x, roofY, supplyShaft1.z), ductW, supplyMat);
            Seg(root.transform, "SupplyRiser_AHU2", new Vector3(supplyShaft2.x, groundY, supplyShaft2.z), new Vector3(supplyShaft2.x, roofY, supplyShaft2.z), ductW, supplyMat);
            Seg(root.transform, "ReturnRiser_AHU1", new Vector3(returnShaft1.x, groundY, returnShaft1.z), new Vector3(returnShaft1.x, roofY, returnShaft1.z), ductW * 0.9f, returnMat);
            Seg(root.transform, "ReturnRiser_AHU2", new Vector3(returnShaft2.x, groundY, returnShaft2.z), new Vector3(returnShaft2.x, roofY, returnShaft2.z), ductW * 0.9f, returnMat);

            Seg(root.transform, "RoofSupply_1", s1 + Vector3.right * 2.0f, new Vector3(supplyShaft1.x, roofY, supplyShaft1.z), ductW * 0.85f, supplyMat);
            Seg(root.transform, "RoofSupply_2", s2 + Vector3.left * 2.0f, new Vector3(supplyShaft2.x, roofY, supplyShaft2.z), ductW * 0.85f, supplyMat);
            Seg(root.transform, "RoofReturn_1", s1 + new Vector3(0.5f, -0.6f, -1.2f), new Vector3(returnShaft1.x, roofY - 0.4f, returnShaft1.z), ductW * 0.8f, returnMat);
            Seg(root.transform, "RoofReturn_2", s2 + new Vector3(-0.5f, -0.6f, -1.2f), new Vector3(returnShaft2.x, roofY - 0.4f, returnShaft2.z), ductW * 0.8f, returnMat);

            // Fat CHW: chiller → vertical riser → both AHUs (supply + return legs)
            Vector3 chwBase = chillerPos + new Vector3(-2.2f, 1.0f, 0f);
            Vector3 chwRiser = new Vector3(28f, 0f, 4f);
            Seg(root.transform, "CHW_from_Chiller", chwBase, new Vector3(chwRiser.x, groundY + 1f, chwRiser.z), chwPipeW, chwMat);
            Seg(root.transform, "CHW_Riser", new Vector3(chwRiser.x, groundY, chwRiser.z), new Vector3(chwRiser.x, roofY, chwRiser.z), chwPipeW, chwMat);
            Seg(root.transform, "CHW_to_AHU1", new Vector3(chwRiser.x, roofY - 0.2f, chwRiser.z), s1 + Vector3.down * 0.4f, chwPipeW * 0.9f, chwMat);
            Seg(root.transform, "CHW_to_AHU2", new Vector3(chwRiser.x, roofY - 0.2f, chwRiser.z), s2 + Vector3.down * 0.4f, chwPipeW * 0.9f, chwMat);
            // CHW return leg (offset)
            Vector3 chwRet = chwRiser + new Vector3(1.2f, 0f, 0f);
            Seg(root.transform, "CHW_Return_Riser", new Vector3(chwRet.x, groundY, chwRet.z), new Vector3(chwRet.x, roofY - 0.5f, chwRet.z), chwPipeW * 0.85f, Trans(new Color(0.35f, 0.65f, 1f, 0.6f)));
            Seg(root.transform, "CHW_Return_to_Chiller", new Vector3(chwRet.x, groundY + 1f, chwRet.z), chwBase + Vector3.forward * 0.8f, chwPipeW * 0.85f, Trans(new Color(0.35f, 0.65f, 1f, 0.6f)));

            // CW loop: chiller ↔ tower
            Vector3 cwChiller = chillerPos + new Vector3(0f, 2.5f, 0f);
            Vector3 cwTower = towerPos + new Vector3(0f, 0.8f, 0f);
            Vector3 cwMid = new Vector3(52f, groundY + 1.5f, -4f);
            Seg(root.transform, "CW_to_Tower_A", cwChiller, cwMid, cwPipeW, cwMat);
            Seg(root.transform, "CW_to_Tower_B", cwMid, new Vector3(towerPos.x, groundY + 1.5f, towerPos.z), cwPipeW, cwMat);
            Seg(root.transform, "CW_Tower_Riser", new Vector3(towerPos.x, groundY + 1.5f, towerPos.z), cwTower, cwPipeW, cwMat);
            Seg(root.transform, "CW_Return_Riser", cwTower + Vector3.right * 1.0f, new Vector3(towerPos.x + 1f, groundY + 1.2f, towerPos.z), cwPipeW * 0.9f, Trans(new Color(0.2f, 0.8f, 0.75f, 0.6f)));
            Seg(root.transform, "CW_Return_to_Chiller", new Vector3(towerPos.x + 1f, groundY + 1.2f, towerPos.z), cwChiller + Vector3.right * 0.8f, cwPipeW * 0.9f, Trans(new Color(0.2f, 0.8f, 0.75f, 0.6f)));

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
                Seg(root.transform, $"SupplyLat_{te.entityId}", new Vector3(shaftS.x, y, shaftS.z), center + Vector3.up * 0.8f, ductW * 0.45f, supplyMat);
                Seg(root.transform, $"ReturnLat_{te.entityId}", center + Vector3.up * 1.1f, new Vector3(shaftR.x, y + 0.35f, shaftR.z), ductW * 0.4f, returnMat);

                var diff = GameObject.CreatePrimitive(PrimitiveType.Cube);
                diff.name = $"Diffuser_{te.entityId}";
                diff.transform.SetParent(root.transform, false);
                diff.transform.position = center + Vector3.up * (b.extents.y * 0.85f);
                diff.transform.localScale = new Vector3(0.9f, 0.1f, 0.9f);
                diff.GetComponent<MeshRenderer>().sharedMaterial = supplyMat;
                KillCol(diff);
                n++;
            }

            // Tag fat pipes
            foreach (Transform c in root.transform)
            {
                if (c.name.StartsWith("CHW_") || c.name.StartsWith("CW_"))
                {
                    var pe = c.gameObject.GetComponent<TwinEntity>() ?? c.gameObject.AddComponent<TwinEntity>();
                    pe.entityId = c.name.ToLowerInvariant();
                    pe.entityType = "plant_pipe";
                    pe.displayName = c.name;
                    pe.isDemoProxy = true;
                }
            }

            var meta = root.AddComponent<TwinEntity>();
            meta.entityId = "mep_xray_demo";
            meta.entityType = "duct_proxy";
            meta.displayName = "DEMO x-ray ducts + CHW/CW plant";
            meta.isDemoProxy = true;
            Debug.Log($"XrayMepBuilder: fat ducts + CHW/CW plant + chiller/tower + {n} floor branches");
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
            // Keep colliders on fat pipes for drone bonk
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
