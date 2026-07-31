using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Large flyable map with Perlin terrain apron + trees around Twin bbox.</summary>
    public class TwinSiteBuilder : MonoBehaviour
    {
        public Vector2 groundSize = new Vector2(1200f, 1000f);
        public Color groundColor = new Color(0.28f, 0.48f, 0.28f);
        public int treeCount = 140;
        public float treeRingPadding = 40f;
        public int terrainResolution = 96;
        public float terrainMaxHeight = 28f;
        public float flatApronRadius = 90f;
        public int terrainSeed = 21;

        public void BuildSite()
        {
            var existing = GameObject.Find("TwinSite");
            if (existing != null) DestroyImmediate(existing);
            var root = new GameObject("TwinSite");

            float cx = 28f, cz = 19f;
            BuildTerrainMesh(root.transform, cx, cz);

            var rng = new System.Random(terrainSeed);
            float innerClear = flatApronRadius;
            float rx = groundSize.x * 0.48f, rz = groundSize.y * 0.48f;
            for (int i = 0; i < treeCount; i++)
            {
                float ang = (float)(i * (360.0 / treeCount) * Mathf.Deg2Rad);
                float band = 0.35f + (float)rng.NextDouble() * 0.55f;
                float jx = (float)(rng.NextDouble() * 22 - 11);
                float jz = (float)(rng.NextDouble() * 22 - 11);
                float x = cx + Mathf.Cos(ang) * (innerClear + band * (rx - innerClear)) + jx;
                float z = cz + Mathf.Sin(ang) * (innerClear + band * (rz - innerClear)) + jz;
                float y = SampleTerrainHeight(x, z, cx, cz);
                var trunk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                trunk.name = $"TreeTrunk_{i}";
                trunk.transform.SetParent(root.transform, false);
                float h = 1.0f + (float)rng.NextDouble() * 0.9f;
                trunk.transform.position = new Vector3(x, y + h, z);
                trunk.transform.localScale = new Vector3(0.45f, h, 0.45f);
                var canopy = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                canopy.name = $"TreeCanopy_{i}";
                canopy.transform.SetParent(root.transform, false);
                canopy.transform.position = new Vector3(x, y + h * 2f + 0.8f, z);
                float cs = 2.0f + (float)rng.NextDouble() * 1.6f;
                canopy.transform.localScale = new Vector3(cs, cs * 1.1f, cs);
                var cmat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                cmat.color = new Color(0.18f, 0.42f + (float)rng.NextDouble() * 0.15f, 0.2f);
                canopy.GetComponent<MeshRenderer>().sharedMaterial = cmat;
            }
            Debug.Log($"TwinSiteBuilder: terrain {groundSize.x}x{groundSize.y} m + {treeCount} trees (seed {terrainSeed})");
        }

        void BuildTerrainMesh(Transform parent, float cx, float cz)
        {
            int res = Mathf.Clamp(terrainResolution, 32, 160);
            var go = new GameObject("TerrainMesh");
            go.transform.SetParent(parent, false);
            var mf = go.AddComponent<MeshFilter>();
            var mr = go.AddComponent<MeshRenderer>();
            var mesh = new Mesh { name = "RandomTerrain" };
            if (res * res > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;

            float halfX = groundSize.x * 0.5f;
            float halfZ = groundSize.y * 0.5f;
            var verts = new Vector3[(res + 1) * (res + 1)];
            var norms = new Vector3[verts.Length];
            var uvs = new Vector2[verts.Length];
            var cols = new Color[verts.Length];

            float ox = terrainSeed * 0.17f;
            float oz = terrainSeed * 0.31f;
            for (int iz = 0; iz <= res; iz++)
            {
                for (int ix = 0; ix <= res; ix++)
                {
                    float u = ix / (float)res;
                    float v = iz / (float)res;
                    float x = cx - halfX + u * groundSize.x;
                    float z = cz - halfZ + v * groundSize.y;
                    float y = SampleTerrainHeight(x, z, cx, cz, ox, oz);
                    int i = iz * (res + 1) + ix;
                    verts[i] = new Vector3(x, y, z);
                    uvs[i] = new Vector2(u, v);
                    // Soft green→brown by height
                    float ht = Mathf.InverseLerp(0f, terrainMaxHeight, y);
                    cols[i] = Color.Lerp(groundColor, new Color(0.42f, 0.38f, 0.28f), ht * 0.55f);
                    norms[i] = Vector3.up;
                }
            }

            var tris = new int[res * res * 6];
            int t = 0;
            for (int iz = 0; iz < res; iz++)
            {
                for (int ix = 0; ix < res; ix++)
                {
                    int i = iz * (res + 1) + ix;
                    tris[t++] = i;
                    tris[t++] = i + res + 1;
                    tris[t++] = i + 1;
                    tris[t++] = i + 1;
                    tris[t++] = i + res + 1;
                    tris[t++] = i + res + 2;
                }
            }

            mesh.vertices = verts;
            mesh.triangles = tris;
            mesh.uv = uvs;
            mesh.colors = cols;
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            mf.sharedMesh = mesh;

            var mat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            mat.color = groundColor;
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", groundColor);
            mr.sharedMaterial = mat;
            go.AddComponent<MeshCollider>();
        }

        float SampleTerrainHeight(float x, float z, float cx, float cz)
        {
            return SampleTerrainHeight(x, z, cx, cz, terrainSeed * 0.17f, terrainSeed * 0.31f);
        }

        float SampleTerrainHeight(float x, float z, float cx, float cz, float ox, float oz)
        {
            float dx = x - cx;
            float dz = z - cz;
            float dist = Mathf.Sqrt(dx * dx + dz * dz);
            float apron = Mathf.SmoothStep(0f, 1f, (dist - flatApronRadius * 0.65f) / (flatApronRadius * 0.55f));
            float n =
                Mathf.PerlinNoise(x * 0.0045f + ox, z * 0.0045f + oz) * 0.55f +
                Mathf.PerlinNoise(x * 0.012f + ox * 2f, z * 0.012f + oz * 2f) * 0.30f +
                Mathf.PerlinNoise(x * 0.035f + ox, z * 0.035f + oz) * 0.15f;
            return Mathf.Max(0f, (n - 0.28f) * terrainMaxHeight * apron);
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
