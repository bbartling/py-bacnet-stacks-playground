using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Schematic x-ray VAV AHU (cool-focused DEMO): OA → filter → mix (RA elbow) → CHW → airplane prop → leave.
    /// Colored airflow proxies for OA / warm RA / cool leave.
    /// </summary>
    public static class XrayAhuFactory
    {
        public static Vector3 DefaultSize = new Vector3(6.0f, 2.4f, 2.5f);

        public static GameObject Build(
            string name,
            string entityId,
            string airLoop,
            Vector3 position,
            Vector3? size = null)
        {
            var dim = size ?? DefaultSize;
            float L = dim.x, H = dim.y, W = dim.z;

            var root = new GameObject(name);
            root.transform.position = position;

            var shellMat = TransMat(new Color(0.55f, 0.58f, 0.62f, 0.20f));
            var frameMat = Mat(new Color(0.30f, 0.32f, 0.36f));
            var filterMat = Mat(new Color(0.78f, 0.74f, 0.55f));
            var coolMat = Mat(new Color(0.28f, 0.52f, 0.92f));
            var fanMat = Mat(new Color(0.16f, 0.16f, 0.18f));
            var damperMat = Mat(new Color(0.50f, 0.55f, 0.42f));
            var oaMat = TransMat(new Color(0.35f, 0.78f, 0.55f, 0.55f));
            var supplyMat = TransMat(new Color(0.25f, 0.48f, 0.95f, 0.55f));
            var returnMat = TransMat(new Color(0.95f, 0.48f, 0.22f, 0.55f));
            var arrowOa = TransMat(new Color(0.30f, 0.85f, 0.50f, 0.65f));
            var arrowRa = TransMat(new Color(1.0f, 0.45f, 0.20f, 0.65f));
            var arrowSa = TransMat(new Color(0.25f, 0.55f, 1.0f, 0.65f));

            Box("Base", root.transform, new Vector3(0, 0.05f, 0), new Vector3(L, 0.1f, W), frameMat);
            Box("Roof", root.transform, new Vector3(0, H, 0), new Vector3(L, 0.08f, W), frameMat);
            Box("Wall_Back", root.transform, new Vector3(0, H * 0.5f, W * 0.48f), new Vector3(L * 0.98f, H * 0.9f, 0.06f), shellMat);
            Box("Wall_Left", root.transform, new Vector3(-L * 0.48f, H * 0.5f, 0), new Vector3(0.06f, H * 0.9f, W * 0.95f), shellMat);
            Box("Wall_Right", root.transform, new Vector3(L * 0.48f, H * 0.5f, 0), new Vector3(0.06f, H * 0.9f, W * 0.95f), shellMat);

            float y = H * 0.48f;

            // OA intake + damper
            Box("OA_Duct", root.transform, new Vector3(-L * 0.52f, H * 0.55f, 0), new Vector3(1.0f, 0.7f, 0.9f), oaMat);
            Box("OA_Hood", root.transform, new Vector3(-L * 0.62f, H * 0.75f, 0), new Vector3(0.55f, 0.4f, 1.0f), frameMat);
            var oaDamp = new GameObject("OA_Dampers");
            oaDamp.transform.SetParent(root.transform, false);
            oaDamp.transform.localPosition = new Vector3(-L * 0.40f, y, 0);
            for (int i = 0; i < 5; i++)
            {
                Box($"OA_Blade_{i}", oaDamp.transform, new Vector3(0, (i - 2) * 0.16f, 0), new Vector3(0.08f, 0.05f, 0.9f), damperMat);
            }

            Box("Filter", root.transform, new Vector3(-L * 0.28f, y, 0), new Vector3(0.14f, H * 0.72f, W * 0.78f), filterMat);
            // Zigzag filter hint
            for (int i = 0; i < 5; i++)
                Box($"FilterZig_{i}", root.transform, new Vector3(-L * 0.28f, y - 0.5f + i * 0.22f, 0), new Vector3(0.18f, 0.04f, W * 0.7f), filterMat);

            // Mix chamber + RA elbow from below (schematic)
            Box("MixBox", root.transform, new Vector3(-L * 0.05f, y, 0), new Vector3(1.35f, H * 0.72f, W * 0.75f),
                TransMat(new Color(0.62f, 0.64f, 0.68f, 0.14f)));
            Box("RA_Vertical", root.transform, new Vector3(-L * 0.08f, H * 0.18f, -W * 0.15f), new Vector3(0.55f, 0.55f, 0.55f), returnMat);
            Box("RA_Elbow", root.transform, new Vector3(-L * 0.08f, H * 0.05f, -W * 0.45f), new Vector3(0.55f, 0.4f, 0.9f), returnMat);
            Box("RA_FromSpace", root.transform, new Vector3(-L * 0.08f, -0.15f, -W * 0.65f), new Vector3(0.7f, 0.45f, 0.7f), returnMat);

            var raDamp = new GameObject("RA_Dampers");
            raDamp.transform.SetParent(root.transform, false);
            raDamp.transform.localPosition = new Vector3(-L * 0.08f, H * 0.28f, 0);
            for (int i = 0; i < 4; i++)
                Box($"RA_Blade_{i}", raDamp.transform, new Vector3(0, i * 0.12f, 0), new Vector3(0.7f, 0.04f, 0.08f), damperMat);

            Box("CoolingCoil", root.transform, new Vector3(L * 0.18f, y, 0), new Vector3(0.32f, H * 0.74f, W * 0.78f), coolMat);
            for (int i = 0; i < 6; i++)
                Box($"CoilFin_{i}", root.transform, new Vector3(L * 0.18f, y - H * 0.28f + i * 0.18f, 0), new Vector3(0.36f, 0.03f, W * 0.76f), coolMat);

            // Airplane prop supply fan
            var supplyPivot = AirplanePropFactory.BuildFacingX(
                root.transform, "SupplyFanPivot", new Vector3(L * 0.36f, y, 0), H * 0.38f, fanMat, 3);
            // Return-path prop on RA riser
            var returnPivot = AirplanePropFactory.BuildFacingX(
                root.transform, "ReturnFanPivot", new Vector3(-L * 0.08f, H * 0.15f, -W * 0.35f), H * 0.22f, fanMat, 2);

            Box("Discharge", root.transform, new Vector3(L * 0.48f, y * 0.95f, 0), new Vector3(0.65f, H * 0.55f, W * 0.6f), frameMat);
            Box("Leave_Duct", root.transform, new Vector3(L * 0.68f, y * 0.75f, 0), new Vector3(1.5f, 0.75f, 0.8f), supplyMat);

            // Named MEP ports (forward = outward flange normal)
            OrthoMepRouter.MakePort(root.transform, "Port_Leave", new Vector3(L * 0.78f, y * 0.75f, 0f), Vector3.right);
            OrthoMepRouter.MakePort(root.transform, "Port_RA", new Vector3(-L * 0.08f, -0.15f, -W * 0.75f), -Vector3.forward);
            OrthoMepRouter.MakePort(root.transform, "Port_CHW_In", new Vector3(L * 0.18f, 0.15f, W * 0.55f), Vector3.forward);
            OrthoMepRouter.MakePort(root.transform, "Port_CHW_Out", new Vector3(L * 0.18f, 0.15f, -W * 0.55f), -Vector3.forward);

            // Colored airflow arrows (OA green, RA warm, Leave cool)
            Arrow("Arrow_OA", root.transform, new Vector3(-L * 0.48f, y + 0.15f, -W * 0.35f), new Vector3(0.55f, 0.12f, 0.22f), arrowOa, 0f);
            Arrow("Arrow_RA", root.transform, new Vector3(-L * 0.08f, H * 0.12f, -W * 0.55f), new Vector3(0.22f, 0.45f, 0.22f), arrowRa, -90f);
            Arrow("Arrow_Leave", root.transform, new Vector3(L * 0.62f, y * 0.75f, -W * 0.35f), new Vector3(0.7f, 0.14f, 0.25f), arrowSa, 0f);

            var te = root.AddComponent<TwinEntity>();
            te.entityId = entityId;
            te.entityType = "ahu_proxy";
            te.displayName = $"{airLoop} (CHW cool x-ray DEMO)";
            te.isDemoProxy = true;

            var spin = root.AddComponent<AhuFanSpin>();
            spin.airLoopName = airLoop;
            spin.ahuType = "VAV_CHW";
            spin.fanWheel = supplyPivot;
            spin.returnFanWheel = returnPivot;
            spin.damperRoot = oaDamp.transform;
            spin.baseRpm = 110f;

            var air = root.AddComponent<AhuAirTempDisplay>();
            air.airLoopName = airLoop;
            air.isAhu2 = airLoop.Contains("2");
            air.BuildSeparateLabels(root.transform, H);

            var flow = root.AddComponent<AhuAirflowArrows>();
            flow.Bind(root.transform);

            return root;
        }

        static void Arrow(string name, Transform parent, Vector3 localPos, Vector3 scale, Material mat, float zRot)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = scale;
            go.transform.localRotation = Quaternion.Euler(0f, 0f, zRot);
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
            KillCol(go);
            // Nose wedge
            var tip = GameObject.CreatePrimitive(PrimitiveType.Cube);
            tip.name = name + "_Tip";
            tip.transform.SetParent(go.transform, false);
            tip.transform.localPosition = new Vector3(0.55f, 0f, 0f);
            tip.transform.localScale = new Vector3(0.35f, 1.4f, 1.4f);
            tip.transform.localRotation = Quaternion.Euler(0f, 0f, 45f);
            tip.GetComponent<MeshRenderer>().sharedMaterial = mat;
            KillCol(tip);
        }

        static void Box(string name, Transform parent, Vector3 localPos, Vector3 scale, Material mat)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = scale;
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

        static Material Mat(Color c)
        {
            var m = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            m.color = c;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            return m;
        }

        static Material TransMat(Color c)
        {
            var m = Mat(c);
            if (m.HasProperty("_Surface")) m.SetFloat("_Surface", 1f);
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.renderQueue = 3000;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            m.color = c;
            return m;
        }
    }

    /// <summary>Subtle pulse on OA/RA/leave arrow proxies.</summary>
    public class AhuAirflowArrows : MonoBehaviour
    {
        Transform[] _arrows;

        public void Bind(Transform root)
        {
            var list = new System.Collections.Generic.List<Transform>();
            foreach (Transform t in root.GetComponentsInChildren<Transform>())
            {
                if (t.name.StartsWith("Arrow_")) list.Add(t);
            }
            _arrows = list.ToArray();
        }

        void Update()
        {
            if (_arrows == null) return;
            float s = 1f + 0.08f * Mathf.Sin(Time.time * 3.5f);
            foreach (var a in _arrows)
            {
                if (a == null) continue;
                var ls = a.localScale;
                // Preserve base proportions via slight uniform nudge on x
                a.localScale = new Vector3(ls.x, ls.y, ls.z); // keep; pulse via position
                a.localPosition += a.right * (0.002f * Mathf.Sin(Time.time * 4f + a.GetInstanceID() * 0.01f));
            }
        }
    }
}
