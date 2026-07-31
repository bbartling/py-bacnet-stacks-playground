using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Classic airplane-style propeller (2–3 long blades) on a SpinPivot (local Y).</summary>
    public static class AirplanePropFactory
    {
        public static Transform Build(
            Transform parent,
            string name,
            Vector3 localPos,
            Quaternion localRot,
            float radius,
            Material mat,
            int blades = 3)
        {
            var pivot = new GameObject(name);
            pivot.transform.SetParent(parent, false);
            pivot.transform.localPosition = localPos;
            pivot.transform.localRotation = localRot;

            var hub = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            hub.name = "Hub";
            hub.transform.SetParent(pivot.transform, false);
            hub.transform.localScale = new Vector3(radius * 0.22f, radius * 0.12f, radius * 0.22f);
            hub.GetComponent<MeshRenderer>().sharedMaterial = mat;
            KillCol(hub);

            blades = Mathf.Clamp(blades, 2, 4);
            for (int i = 0; i < blades; i++)
            {
                float ang = i * (360f / blades);
                var blade = GameObject.CreatePrimitive(PrimitiveType.Cube);
                blade.name = $"PropBlade_{i}";
                blade.transform.SetParent(pivot.transform, false);
                // Long thin airplane blade along local +X, spun around Y
                blade.transform.localRotation = Quaternion.Euler(12f, ang, 0f);
                blade.transform.localPosition = Quaternion.Euler(0f, ang, 0f) * new Vector3(radius * 0.55f, 0.02f, 0f);
                blade.transform.localScale = new Vector3(radius * 1.15f, radius * 0.045f, radius * 0.14f);
                blade.GetComponent<MeshRenderer>().sharedMaterial = mat;
                KillCol(blade);
            }
            return pivot.transform;
        }

        /// <summary>Airflow along +X: local Y of pivot maps to world +X.</summary>
        public static Transform BuildFacingX(Transform parent, string name, Vector3 localPos, float radius, Material mat, int blades = 3) =>
            Build(parent, name, localPos, Quaternion.Euler(0f, 0f, -90f), radius, mat, blades);

        /// <summary>Spin about world up (cooling tower).</summary>
        public static Transform BuildFacingUp(Transform parent, string name, Vector3 localPos, float radius, Material mat, int blades = 3) =>
            Build(parent, name, localPos, Quaternion.identity, radius, mat, blades);

        static void KillCol(GameObject go)
        {
            var c = go.GetComponent<Collider>();
            if (c == null) return;
            if (Application.isPlaying) Object.Destroy(c);
            else Object.DestroyImmediate(c);
        }
    }
}
