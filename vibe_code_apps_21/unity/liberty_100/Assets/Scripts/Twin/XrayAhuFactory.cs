using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Cutaway / x-ray VAV AHU matching IDF VAV Sys (OA→filter→mix→CHW→HW→fan).
    /// Default footprint matches manually tuned roof size (~6 × 4.3 × 2.5 m).
    /// </summary>
    public static class XrayAhuFactory
    {
        // User-tuned visual scale from Liberty100Twin scene
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

            var shellMat = TransMat(new Color(0.55f, 0.58f, 0.62f, 0.22f));
            var frameMat = Mat(new Color(0.35f, 0.37f, 0.40f));
            var filterMat = Mat(new Color(0.75f, 0.72f, 0.55f));
            var coolMat = Mat(new Color(0.35f, 0.55f, 0.85f));
            var heatMat = Mat(new Color(0.85f, 0.40f, 0.32f));
            var fanMat = Mat(new Color(0.22f, 0.22f, 0.25f));
            var supplyMat = TransMat(new Color(0.25f, 0.45f, 0.85f, 0.55f));
            var returnMat = TransMat(new Color(0.85f, 0.45f, 0.25f, 0.55f));

            // Floor slab of cabinet
            Box("Base", root.transform, new Vector3(0, 0.05f, 0), new Vector3(L, 0.1f, W), frameMat);
            // Roof
            Box("Roof", root.transform, new Vector3(0, H, 0), new Vector3(L, 0.08f, W), frameMat);
            // Back wall (keep) — open -Z side for cutaway viewing
            Box("Wall_Back", root.transform, new Vector3(0, H * 0.5f, W * 0.48f), new Vector3(L * 0.98f, H * 0.9f, 0.06f), shellMat);
            Box("Wall_Left", root.transform, new Vector3(-L * 0.48f, H * 0.5f, 0), new Vector3(0.06f, H * 0.9f, W * 0.95f), shellMat);
            Box("Wall_Right", root.transform, new Vector3(L * 0.48f, H * 0.5f, 0), new Vector3(0.06f, H * 0.9f, W * 0.95f), shellMat);

            // Stages along +X: OA | Filter | Mix | Cool | Heat | Fan/Discharge
            float y = H * 0.45f;
            float sec = L / 6.2f;

            // OA intake hood
            Box("OA_Intake", root.transform, new Vector3(-L * 0.42f, H * 0.85f, 0), new Vector3(sec * 0.7f, 0.35f, W * 0.55f), frameMat);
            // Filter bank
            Box("Filter", root.transform, new Vector3(-L * 0.30f, y, 0), new Vector3(0.12f, H * 0.7f, W * 0.75f), filterMat);
            // Mixing chamber (empty volume marker)
            Box("MixBox", root.transform, new Vector3(-L * 0.12f, y, 0), new Vector3(sec * 0.9f, H * 0.65f, W * 0.7f), TransMat(new Color(0.6f, 0.6f, 0.65f, 0.12f)));
            // Cooling coil (CHW)
            Box("CoolingCoil", root.transform, new Vector3(L * 0.05f, y, 0), new Vector3(0.18f, H * 0.7f, W * 0.75f), coolMat);
            // Heating coil (HW)
            Box("HeatingCoil", root.transform, new Vector3(L * 0.18f, y, 0), new Vector3(0.18f, H * 0.7f, W * 0.75f), heatMat);

            // Supply fan wheel (spin target)
            var fan = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            fan.name = "FanWheel";
            fan.transform.SetParent(root.transform, false);
            fan.transform.localPosition = new Vector3(L * 0.32f, y, 0);
            fan.transform.localRotation = Quaternion.Euler(0f, 0f, 90f);
            fan.transform.localScale = new Vector3(H * 0.55f, 0.22f, H * 0.55f);
            fan.GetComponent<MeshRenderer>().sharedMaterial = fanMat;
            KillCol(fan);
            for (int i = 0; i < 6; i++)
            {
                float ang = i * 60f * Mathf.Deg2Rad;
                var blade = GameObject.CreatePrimitive(PrimitiveType.Cube);
                blade.name = $"FanBlade_{i}";
                blade.transform.SetParent(fan.transform, false);
                blade.transform.localPosition = new Vector3(Mathf.Cos(ang) * 0.35f, 0f, Mathf.Sin(ang) * 0.35f);
                blade.transform.localScale = new Vector3(0.55f, 0.08f, 0.12f);
                blade.GetComponent<MeshRenderer>().sharedMaterial = fanMat;
                KillCol(blade);
            }

            // Discharge plenum + supply stub (blue)
            Box("Discharge", root.transform, new Vector3(L * 0.42f, y * 0.9f, 0), new Vector3(sec * 0.6f, H * 0.5f, W * 0.55f), frameMat);
            Box("SupplyStub", root.transform, new Vector3(L * 0.52f, y * 0.7f, 0), new Vector3(0.8f, 0.45f, 0.55f), supplyMat);
            // Return stub into mix (orange)
            Box("ReturnStub", root.transform, new Vector3(-L * 0.05f, H * 0.15f, -W * 0.35f), new Vector3(0.55f, 0.4f, 0.7f), returnMat);

            var te = root.AddComponent<TwinEntity>();
            te.entityId = entityId;
            te.entityType = "ahu_proxy";
            te.displayName = $"{airLoop} (VAV_CHW x-ray DEMO)";
            te.isDemoProxy = true;

            var spin = root.AddComponent<AhuFanSpin>();
            spin.airLoopName = airLoop;
            spin.ahuType = "VAV_CHW";
            spin.fanWheel = fan.transform;
            spin.baseRpm = 70f;

            // Three separate air-temp labels (no mash)
            var air = root.AddComponent<AhuAirTempDisplay>();
            air.airLoopName = airLoop;
            air.isAhu2 = airLoop.Contains("2");
            air.BuildSeparateLabels(root.transform, H);

            return root;
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
}
