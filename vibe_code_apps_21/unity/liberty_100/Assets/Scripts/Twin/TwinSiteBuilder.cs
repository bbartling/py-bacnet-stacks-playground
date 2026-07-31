using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Green ground plane + simple tree proxies around Twin bbox.</summary>
    public class TwinSiteBuilder : MonoBehaviour
    {
        public Vector2 groundSize = new Vector2(120f, 100f);
        public Color groundColor = new Color(0.28f, 0.48f, 0.28f);
        public int treeCount = 24;
        public float treeRingPadding = 12f;

        public void BuildSite()
        {
            var existing = GameObject.Find("TwinSite");
            if (existing != null) DestroyImmediate(existing);
            var root = new GameObject("TwinSite");

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            ground.transform.SetParent(root.transform, false);
            ground.transform.localScale = new Vector3(groundSize.x / 10f, 1f, groundSize.y / 10f);
            ground.transform.position = new Vector3(28f, -0.05f, 19f);
            var mat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            mat.color = groundColor;
            ground.GetComponent<MeshRenderer>().sharedMaterial = mat;

            var rng = new System.Random(21);
            float cx = 28f, cz = 19f;
            float rx = groundSize.x * 0.4f, rz = groundSize.y * 0.4f;
            for (int i = 0; i < treeCount; i++)
            {
                float ang = (float)(i * (360.0 / treeCount) * Mathf.Deg2Rad);
                float jx = (float)(rng.NextDouble() * 4 - 2);
                float jz = (float)(rng.NextDouble() * 4 - 2);
                float x = cx + Mathf.Cos(ang) * (rx + treeRingPadding) + jx;
                float z = cz + Mathf.Sin(ang) * (rz + treeRingPadding) + jz;
                var trunk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                trunk.name = $"TreeTrunk_{i}";
                trunk.transform.SetParent(root.transform, false);
                trunk.transform.position = new Vector3(x, 1.2f, z);
                trunk.transform.localScale = new Vector3(0.35f, 1.2f, 0.35f);
                var canopy = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                canopy.name = $"TreeCanopy_{i}";
                canopy.transform.SetParent(root.transform, false);
                canopy.transform.position = new Vector3(x, 3.2f, z);
                canopy.transform.localScale = new Vector3(2.2f, 2.4f, 2.2f);
                var cmat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                cmat.color = new Color(0.18f, 0.42f + (float)rng.NextDouble() * 0.15f, 0.2f);
                canopy.GetComponent<MeshRenderer>().sharedMaterial = cmat;
            }
            Debug.Log("TwinSiteBuilder: ground + trees ready");
        }

#if UNITY_EDITOR
        [UnityEditor.MenuItem("Vibe21/Twin/Build Green Site")]
        public static void MenuBuild()
        {
            var go = GameObject.Find("TwinSiteBuilder");
            if (go == null) go = new GameObject("TwinSiteBuilder");
            var b = go.GetComponent<TwinSiteBuilder>() ?? go.AddComponent<TwinSiteBuilder>();
            b.BuildSite();
        }
#endif
    }
}
