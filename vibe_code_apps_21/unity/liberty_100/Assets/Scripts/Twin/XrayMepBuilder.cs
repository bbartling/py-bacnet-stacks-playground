using System.Collections.Generic;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Fat x-ray MEP with Manhattan routing into equipment ports + particle flow FX.
    /// Supply/return ducts + CHW/CW plant pipes (no HW to AHUs).
    /// </summary>
    public class XrayMepBuilder : MonoBehaviour
    {
        public float ductW = 0.95f;
        public float chwPipeW = 0.55f;
        public float cwPipeW = 0.48f;
        public float stubLen = 0.55f;

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
            var chwRetMat = Trans(new Color(0.35f, 0.65f, 1f, 0.6f));
            var cwMat = Trans(new Color(0.1f, 0.7f, 0.72f, 0.65f));
            var cwRetMat = Trans(new Color(0.2f, 0.8f, 0.75f, 0.6f));

            var ahu1 = FindAhu("ahu_proxy_vav_sys_1");
            var ahu2 = FindAhu("ahu_proxy_vav_sys_2");

            Vector3 s1 = ahu1 != null ? ahu1.position : new Vector3(12f, 25f, 19f);
            Vector3 s2 = ahu2 != null ? ahu2.position : new Vector3(45f, 25f, 19f);
            float roofY = Mathf.Max(s1.y, s2.y) + 1.0f;
            float groundY = 1.2f;

            Vector3 chillerPos = new Vector3(28f, roofY - 0.6f, 12f);
            Vector3 towerPos = new Vector3(52f, roofY - 0.5f, 22f);
            var plantRoot = XrayPlantFactory.Build(root.transform, chillerPos, towerPos);
            var chiller = plantRoot != null ? plantRoot.transform.Find("MainChiller") : null;
            var tower = plantRoot != null ? plantRoot.transform.Find("CoolingTower") : null;

            Vector3 supplyShaft1 = new Vector3(s1.x - 1.5f, 0f, s1.z + 2.0f);
            Vector3 supplyShaft2 = new Vector3(s2.x + 1.5f, 0f, s2.z + 2.0f);
            Vector3 returnShaft1 = new Vector3(s1.x + 1.2f, 0f, s1.z - 1.5f);
            Vector3 returnShaft2 = new Vector3(s2.x - 1.2f, 0f, s2.z - 1.5f);

            var fx = MepFlowFx.EnsureOn(root);
            fx.Clear();
            var fxSupply = new List<Vector3[]>();
            var fxReturn = new List<Vector3[]>();
            var allChwSegs = new List<Vector3[]>();
            var allCwSegs = new List<Vector3[]>();

            fxSupply.AddRange(OrthoMepRouter.Riser(root.transform, "SupplyRiser_AHU1", supplyShaft1, groundY, roofY, ductW, supplyMat));
            fxSupply.AddRange(OrthoMepRouter.Riser(root.transform, "SupplyRiser_AHU2", supplyShaft2, groundY, roofY, ductW, supplyMat));
            fxReturn.AddRange(OrthoMepRouter.Riser(root.transform, "ReturnRiser_AHU1", returnShaft1, groundY, roofY, ductW * 0.9f, returnMat));
            fxReturn.AddRange(OrthoMepRouter.Riser(root.transform, "ReturnRiser_AHU2", returnShaft2, groundY, roofY, ductW * 0.9f, returnMat));

            var leave1 = PortOrFallback(ahu1, "Port_Leave", s1 + Vector3.right * 2f, Vector3.right);
            var leave2 = PortOrFallback(ahu2, "Port_Leave", s2 + Vector3.left * 2f, Vector3.left);
            var ra1 = PortOrFallback(ahu1, "Port_RA", s1 + new Vector3(0.5f, -0.6f, -1.2f), -Vector3.forward);
            var ra2 = PortOrFallback(ahu2, "Port_RA", s2 + new Vector3(-0.5f, -0.6f, -1.2f), -Vector3.forward);

            var shaftTopS1 = MakeTempPort(new Vector3(supplyShaft1.x, roofY, supplyShaft1.z), Vector3.up);
            var shaftTopS2 = MakeTempPort(new Vector3(supplyShaft2.x, roofY, supplyShaft2.z), Vector3.up);
            var shaftTopR1 = MakeTempPort(new Vector3(returnShaft1.x, roofY - 0.4f, returnShaft1.z), Vector3.up);
            var shaftTopR2 = MakeTempPort(new Vector3(returnShaft2.x, roofY - 0.4f, returnShaft2.z), Vector3.up);

            fxSupply.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "RoofSupply_1", leave1, shaftTopS1, ductW * 0.85f, supplyMat, stubLen, OrthoMepRouter.AxisOrder.XZY));
            fxSupply.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "RoofSupply_2", leave2, shaftTopS2, ductW * 0.85f, supplyMat, stubLen, OrthoMepRouter.AxisOrder.XZY));
            fxReturn.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "RoofReturn_1", ra1, shaftTopR1, ductW * 0.8f, returnMat, stubLen, OrthoMepRouter.AxisOrder.YXZ));
            fxReturn.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "RoofReturn_2", ra2, shaftTopR2, ductW * 0.8f, returnMat, stubLen, OrthoMepRouter.AxisOrder.YXZ));

            var chwHdr = PortOrFallback(chiller, "Port_CHW_Header", chillerPos + new Vector3(-2.7f, 1f, 0f), -Vector3.right);
            var chwRetHdr = PortOrFallback(chiller, "Port_CHW_Return", chillerPos + new Vector3(-2.7f, 1f, 0.7f), -Vector3.right);
            var chwIn1 = PortOrFallback(ahu1, "Port_CHW_In", s1 + new Vector3(0f, 0.15f, 1.2f), Vector3.forward);
            var chwIn2 = PortOrFallback(ahu2, "Port_CHW_In", s2 + new Vector3(0f, 0.15f, 1.2f), Vector3.forward);
            var chwOut1 = PortOrFallback(ahu1, "Port_CHW_Out", s1 + new Vector3(0f, 0.15f, -1.2f), -Vector3.forward);
            var chwOut2 = PortOrFallback(ahu2, "Port_CHW_Out", s2 + new Vector3(0f, 0.15f, -1.2f), -Vector3.forward);

            allChwSegs.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "CHW_to_AHU1", chwHdr, chwIn1, chwPipeW, chwMat, stubLen, OrthoMepRouter.AxisOrder.XZY, true));
            allChwSegs.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "CHW_to_AHU2", chwHdr, chwIn2, chwPipeW, chwMat, stubLen, OrthoMepRouter.AxisOrder.XZY, true));
            allChwSegs.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "CHW_Return_AHU1", chwOut1, chwRetHdr, chwPipeW * 0.85f, chwRetMat, stubLen, OrthoMepRouter.AxisOrder.XZY, true));
            allChwSegs.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "CHW_Return_AHU2", chwOut2, chwRetHdr, chwPipeW * 0.85f, chwRetMat, stubLen, OrthoMepRouter.AxisOrder.XZY, true));

            var cwOut = PortOrFallback(chiller, "Port_CW_Out", chillerPos + new Vector3(0f, 2.5f, 0.6f), Vector3.forward);
            var cwRet = PortOrFallback(chiller, "Port_CW_Return", chillerPos + new Vector3(0.8f, 2.5f, 0f), Vector3.right);
            var cwTowerIn = PortOrFallback(tower, "Port_CW_In", towerPos + new Vector3(0f, 0.8f, -2.4f), -Vector3.forward);
            var cwTowerOut = PortOrFallback(tower, "Port_CW_Out", towerPos + new Vector3(2.4f, 0.8f, 0f), Vector3.right);

            allCwSegs.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "CW_to_Tower", cwOut, cwTowerIn, cwPipeW, cwMat, stubLen, OrthoMepRouter.AxisOrder.XZY, true));
            allCwSegs.AddRange(OrthoMepRouter.PathStubThenOrtho(
                root.transform, "CW_Return", cwTowerOut, cwRet, cwPipeW * 0.9f, cwRetMat, stubLen, OrthoMepRouter.AxisOrder.XZY, true));

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
                var diffPos = center + Vector3.up * (b.extents.y * 0.85f);

                var shaftPortS = MakeTempPort(new Vector3(shaftS.x, y, shaftS.z), Vector3.right);
                var shaftPortR = MakeTempPort(new Vector3(shaftR.x, y + 0.35f, shaftR.z), Vector3.left);
                var diffSupply = MakeTempPort(diffPos + Vector3.up * 0.15f, Vector3.down);
                var diffReturn = MakeTempPort(diffPos + Vector3.up * 0.45f, Vector3.up);

                OrthoMepRouter.PathStubThenOrtho(
                    root.transform, $"SupplyLat_{te.entityId}", shaftPortS, diffSupply, ductW * 0.45f, supplyMat, 0.35f, OrthoMepRouter.AxisOrder.XZY);
                OrthoMepRouter.PathStubThenOrtho(
                    root.transform, $"ReturnLat_{te.entityId}", diffReturn, shaftPortR, ductW * 0.4f, returnMat, 0.35f, OrthoMepRouter.AxisOrder.XZY);

                var diff = GameObject.CreatePrimitive(PrimitiveType.Cube);
                diff.name = $"Diffuser_{te.entityId}";
                diff.transform.SetParent(root.transform, false);
                diff.transform.position = diffPos;
                diff.transform.localScale = new Vector3(0.9f, 0.1f, 0.9f);
                diff.GetComponent<MeshRenderer>().sharedMaterial = supplyMat;
                KillCol(diff);
                n++;
            }

            fx.AddAlongPath(fxSupply, new Color(0.35f, 0.65f, 1f, 0.55f), true, 3.5f);
            fx.AddAlongPath(fxReturn, new Color(1f, 0.5f, 0.25f, 0.55f), true, 3.0f);
            fx.AddAlongPath(allChwSegs, new Color(0.3f, 0.7f, 1f, 0.65f), false, 1.8f);
            fx.AddAlongPath(allCwSegs, new Color(0.2f, 0.9f, 0.85f, 0.65f), false, 1.6f);
            if (tower != null) fx.AddTowerFx(tower);
            fx.SetRunning(true, 1f);

            var plantCtrl = plantRoot != null ? plantRoot.GetComponent<PlantVisualController>() : null;
            if (plantCtrl != null)
                plantCtrl.flowFx = fx;

            var meta = root.AddComponent<TwinEntity>();
            meta.entityId = "mep_xray_demo";
            meta.entityType = "duct_proxy";
            meta.displayName = "DEMO ortho ducts + CHW/CW plant + flow FX";
            meta.isDemoProxy = true;
            Debug.Log($"XrayMepBuilder: ortho MEP + flow FX + chiller/tower + {n} floor branches");
        }

        static Transform FindAhu(string entityId)
        {
            foreach (var te in FindObjectsByType<TwinEntity>())
                if (te.entityType == "ahu_proxy" && te.entityId == entityId)
                    return te.transform;
            return null;
        }

        static Transform PortOrFallback(Transform equipment, string portName, Vector3 worldFallback, Vector3 outward)
        {
            if (equipment != null)
            {
                var t = equipment.Find(portName);
                if (t != null) return t;
                foreach (var c in equipment.GetComponentsInChildren<Transform>())
                    if (c.name == portName) return c;
            }
            return MakeTempPort(worldFallback, outward);
        }

        static Transform MakeTempPort(Vector3 worldPos, Vector3 outward)
        {
            var go = new GameObject("TempPort");
            go.hideFlags = HideFlags.HideAndDontSave;
            go.transform.position = worldPos;
            if (outward.sqrMagnitude > 1e-6f)
                go.transform.rotation = Quaternion.LookRotation(outward.normalized, Vector3.up);
            return go.transform;
        }

        static Bounds BoundsOf(Transform t)
        {
            var rs = t.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return new Bounds(t.position, Vector3.one * 4f);
            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            return b;
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
