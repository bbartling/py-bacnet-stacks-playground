using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Cutaway VAV AHU (cool-focused DEMO): OA + RA → mix dampers → filter → CHW coil → supply fan → leave duct.
    /// Return-path fan on RA stub. No HW coil in cabinet (E+ HW/boiler/reheat omitted for clarity).
    /// Fans use SpinPivot local-Y spin (same fix as drone props).
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

            var shellMat = TransMat(new Color(0.55f, 0.58f, 0.62f, 0.22f));
            var frameMat = Mat(new Color(0.32f, 0.34f, 0.38f));
            var filterMat = Mat(new Color(0.78f, 0.74f, 0.55f));
            var coolMat = Mat(new Color(0.30f, 0.55f, 0.90f));
            var fanMat = Mat(new Color(0.18f, 0.18f, 0.22f));
            var damperMat = Mat(new Color(0.55f, 0.58f, 0.45f));
            var oaMat = TransMat(new Color(0.45f, 0.75f, 0.55f, 0.55f));
            var supplyMat = TransMat(new Color(0.25f, 0.45f, 0.90f, 0.55f));
            var returnMat = TransMat(new Color(0.90f, 0.48f, 0.25f, 0.55f));

            Box("Base", root.transform, new Vector3(0, 0.05f, 0), new Vector3(L, 0.1f, W), frameMat);
            Box("Roof", root.transform, new Vector3(0, H, 0), new Vector3(L, 0.08f, W), frameMat);
            Box("Wall_Back", root.transform, new Vector3(0, H * 0.5f, W * 0.48f), new Vector3(L * 0.98f, H * 0.9f, 0.06f), shellMat);
            Box("Wall_Left", root.transform, new Vector3(-L * 0.48f, H * 0.5f, 0), new Vector3(0.06f, H * 0.9f, W * 0.95f), shellMat);
            Box("Wall_Right", root.transform, new Vector3(L * 0.48f, H * 0.5f, 0), new Vector3(0.06f, H * 0.9f, W * 0.95f), shellMat);

            float y = H * 0.48f;

            // OA intake duct (green) from above/outside into mix
            Box("OA_Duct", root.transform, new Vector3(-L * 0.48f, H * 0.92f, 0), new Vector3(1.1f, 0.55f, 0.85f), oaMat);
            Box("OA_Hood", root.transform, new Vector3(-L * 0.55f, H * 1.15f, 0), new Vector3(0.7f, 0.35f, 0.9f), frameMat);

            // RA return duct from space into mix (orange)
            Box("RA_Duct", root.transform, new Vector3(-L * 0.22f, H * 0.18f, -W * 0.55f), new Vector3(0.9f, 0.55f, 1.2f), returnMat);

            // Mix chamber
            Box("MixBox", root.transform, new Vector3(-L * 0.18f, y, 0), new Vector3(1.1f, H * 0.7f, W * 0.72f),
                TransMat(new Color(0.6f, 0.62f, 0.66f, 0.14f)));

            // Opposed-blade mix dampers (OA bank + RA bank)
            var damperRoot = new GameObject("MixDampers");
            damperRoot.transform.SetParent(root.transform, false);
            damperRoot.transform.localPosition = new Vector3(-L * 0.28f, y, 0);
            BuildDamperBank(damperRoot.transform, "OA_Dampers", new Vector3(-0.15f, 0.15f, 0), 5, damperMat);
            BuildDamperBank(damperRoot.transform, "RA_Dampers", new Vector3(0.2f, -0.2f, 0), 5, damperMat);

            Box("Filter", root.transform, new Vector3(-L * 0.02f, y, 0), new Vector3(0.14f, H * 0.72f, W * 0.78f), filterMat);
            Box("CoolingCoil", root.transform, new Vector3(L * 0.12f, y, 0), new Vector3(0.28f, H * 0.74f, W * 0.78f), coolMat);
            // Coil fins detail
            for (int i = 0; i < 6; i++)
            {
                Box($"CoilFin_{i}", root.transform,
                    new Vector3(L * 0.12f, y - H * 0.28f + i * 0.18f, 0),
                    new Vector3(0.32f, 0.03f, W * 0.76f), coolMat);
            }

            // Supply fan — SpinPivot local Y = airflow (+X)
            var supplyPivot = MakeFanPivot(root.transform, "SupplyFanPivot",
                new Vector3(L * 0.32f, y, 0), H * 0.42f, fanMat);

            // Return-path fan on RA stub
            var returnPivot = MakeFanPivot(root.transform, "ReturnFanPivot",
                new Vector3(-L * 0.22f, H * 0.18f, -W * 0.35f), H * 0.28f, fanMat);

            // Discharge + leave duct to space (blue)
            Box("Discharge", root.transform, new Vector3(L * 0.44f, y * 0.95f, 0), new Vector3(0.7f, H * 0.55f, W * 0.6f), frameMat);
            Box("Leave_Duct", root.transform, new Vector3(L * 0.62f, y * 0.75f, 0), new Vector3(1.4f, 0.7f, 0.75f), supplyMat);

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
            spin.damperRoot = damperRoot.transform;
            spin.baseRpm = 90f;

            var air = root.AddComponent<AhuAirTempDisplay>();
            air.airLoopName = airLoop;
            air.isAhu2 = airLoop.Contains("2");
            air.BuildSeparateLabels(root.transform, H);

            return root;
        }

        static Transform MakeFanPivot(Transform parent, string name, Vector3 localPos, float radius, Material fanMat)
        {
            var pivot = new GameObject(name);
            pivot.transform.SetParent(parent, false);
            pivot.transform.localPosition = localPos;
            // Local Y → world +X (airflow axis)
            pivot.transform.localRotation = Quaternion.Euler(0f, 0f, -90f);

            var hub = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            hub.name = "Hub";
            hub.transform.SetParent(pivot.transform, false);
            hub.transform.localScale = new Vector3(radius * 0.35f, radius * 0.12f, radius * 0.35f);
            hub.GetComponent<MeshRenderer>().sharedMaterial = fanMat;
            KillCol(hub);

            var disk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            disk.name = "FanDisk";
            disk.transform.SetParent(pivot.transform, false);
            disk.transform.localPosition = new Vector3(0f, 0.02f, 0f);
            disk.transform.localScale = new Vector3(radius * 1.8f, radius * 0.04f, radius * 1.8f);
            disk.GetComponent<MeshRenderer>().sharedMaterial = fanMat;
            KillCol(disk);

            for (int i = 0; i < 6; i++)
            {
                float ang = i * 60f * Mathf.Deg2Rad;
                var blade = GameObject.CreatePrimitive(PrimitiveType.Cube);
                blade.name = $"Blade_{i}";
                blade.transform.SetParent(pivot.transform, false);
                blade.transform.localPosition = new Vector3(Mathf.Cos(ang) * radius * 0.55f, 0.03f, Mathf.Sin(ang) * radius * 0.55f);
                blade.transform.localRotation = Quaternion.Euler(0f, -i * 60f, 15f);
                blade.transform.localScale = new Vector3(radius * 0.95f, radius * 0.06f, radius * 0.22f);
                blade.GetComponent<MeshRenderer>().sharedMaterial = fanMat;
                KillCol(blade);
            }
            return pivot.transform;
        }

        static void BuildDamperBank(Transform parent, string name, Vector3 offset, int blades, Material mat)
        {
            var bank = new GameObject(name);
            bank.transform.SetParent(parent, false);
            bank.transform.localPosition = offset;
            for (int i = 0; i < blades; i++)
            {
                var blade = GameObject.CreatePrimitive(PrimitiveType.Cube);
                blade.name = $"Blade_{i}";
                blade.transform.SetParent(bank.transform, false);
                blade.transform.localPosition = new Vector3(0f, (i - blades * 0.5f) * 0.14f, 0f);
                blade.transform.localScale = new Vector3(0.08f, 0.04f, 0.85f);
                blade.transform.localRotation = Quaternion.Euler(0f, 0f, 25f);
                blade.GetComponent<MeshRenderer>().sharedMaterial = mat;
                KillCol(blade);
            }
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
