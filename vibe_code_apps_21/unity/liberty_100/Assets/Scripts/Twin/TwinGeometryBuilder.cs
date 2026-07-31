using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Builds Floor×AHU massing from StreamingAssets Twin geometry (E+ meters → Unity Y-up).
    /// Does not invent room/VAV polygons.
    /// </summary>
    public class TwinGeometryBuilder : MonoBehaviour
    {
        public string geometryFileName = "Twin/unity_geometry.json";
        public Material wallMaterial;
        public Material floorMaterial;
        public Material roofMaterial;
        public Material windowMaterial;
        /// <summary>Push windows slightly outward (m) to avoid z-fighting with parent walls.</summary>
        public float windowOutsetM = 0.04f;
        public Transform root;

        [Serializable] class Vert { public float x, y, z; }
        [Serializable] class Surface
        {
            public string name;
            public string surface_type;
            public string zone;
            public Vert[] vertices_m;
        }
        [Serializable] class Zone
        {
            public string name;
            public string entity_id;
        }
        [Serializable] class GeoRoot
        {
            public string twin_run_id;
            public Zone[] zones;
            public Surface[] surfaces;
        }

        static Vector3 EpToUnity(Vert v) => new Vector3(v.x, v.z, v.y);

        public void BuildFromStreamingAssets()
        {
            var path = Path.Combine(Application.streamingAssetsPath, geometryFileName);
            if (!File.Exists(path))
            {
                Debug.LogError($"Twin geometry missing: {path}");
                return;
            }
            BuildFromJson(File.ReadAllText(path));
        }

        public void BuildFromJson(string json)
        {
            var data = JsonUtility.FromJson<GeoRoot>(json);
            if (data?.surfaces == null || data.surfaces.Length == 0)
            {
                Debug.LogError("Twin geometry has no surfaces");
                return;
            }

            if (root == null)
            {
                var go = GameObject.Find("Liberty100Massing");
                if (go == null) go = new GameObject("Liberty100Massing");
                root = go.transform;
            }

            for (int i = root.childCount - 1; i >= 0; i--)
                DestroyImmediate(root.GetChild(i).gameObject);

            var zoneParents = new Dictionary<string, Transform>();
            if (data.zones != null)
            {
                foreach (var z in data.zones)
                {
                    var zg = new GameObject(z.name);
                    zg.transform.SetParent(root, false);
                    var te = zg.AddComponent<TwinEntity>();
                    te.entityId = z.entity_id;
                    te.entityType = "zone";
                    te.displayName = z.name;
                    zoneParents[z.name] = zg.transform;
                }
            }

            EnsureMaterials();
            int built = 0;
            foreach (var s in data.surfaces)
            {
                if (s.vertices_m == null || s.vertices_m.Length < 3) continue;
                Transform parent = root;
                if (!string.IsNullOrEmpty(s.zone) && zoneParents.TryGetValue(s.zone, out var zp))
                    parent = zp;

                var go = new GameObject(s.name);
                go.transform.SetParent(parent, false);
                var mf = go.AddComponent<MeshFilter>();
                var mr = go.AddComponent<MeshRenderer>();
                mf.sharedMesh = BuildQuadOrPoly(s.vertices_m, s.surface_type);
                mr.sharedMaterial = PickMaterial(s.surface_type);
                if (IsWindow(s.surface_type))
                {
                    // Transparent glass needs alpha; URP Lit supports Surface Type Transparent when set.
                    mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                }
                var te = go.AddComponent<TwinEntity>();
                te.entityType = IsWindow(s.surface_type) ? "window" : "surface";
                te.displayName = s.name;
                if (!string.IsNullOrEmpty(s.zone) && zoneParents.TryGetValue(s.zone, out var zpt))
                {
                    var ze = zpt.GetComponent<TwinEntity>();
                    if (ze != null) te.entityId = ze.entityId;
                }
                built++;
            }
            Debug.Log($"TwinGeometryBuilder: {built} surfaces from {data.twin_run_id}");
        }

        void EnsureMaterials()
        {
            if (wallMaterial == null)
            {
                wallMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                wallMaterial.color = new Color(0.72f, 0.78f, 0.85f, 1f);
            }
            if (floorMaterial == null)
            {
                floorMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                floorMaterial.color = new Color(0.45f, 0.48f, 0.52f, 1f);
            }
            if (roofMaterial == null)
            {
                roofMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                roofMaterial.color = new Color(0.35f, 0.38f, 0.42f, 1f);
            }
            if (windowMaterial == null)
            {
                windowMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                // E+ Exterior Window Glass look — blue-ish translucent pane
                windowMaterial.color = new Color(0.35f, 0.55f, 0.75f, 0.45f);
                if (windowMaterial.HasProperty("_Surface"))
                    windowMaterial.SetFloat("_Surface", 1f); // Transparent
                if (windowMaterial.HasProperty("_Blend"))
                    windowMaterial.SetFloat("_Blend", 0f);
                if (windowMaterial.HasProperty("_BaseColor"))
                    windowMaterial.SetColor("_BaseColor", new Color(0.35f, 0.55f, 0.75f, 0.45f));
                windowMaterial.SetFloat("_Metallic", 0.1f);
                windowMaterial.SetFloat("_Smoothness", 0.85f);
                windowMaterial.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                windowMaterial.renderQueue = 3000;
            }
        }

        static bool IsWindow(string surfaceType) =>
            !string.IsNullOrEmpty(surfaceType) && surfaceType.ToLowerInvariant().Contains("window");

        Material PickMaterial(string surfaceType)
        {
            if (string.IsNullOrEmpty(surfaceType)) return wallMaterial;
            var t = surfaceType.ToLowerInvariant();
            if (t.Contains("window")) return windowMaterial;
            if (t.Contains("floor")) return floorMaterial;
            if (t.Contains("roof") || t.Contains("ceiling")) return roofMaterial;
            return wallMaterial;
        }

        Mesh BuildQuadOrPoly(Vert[] verts, string surfaceType)
        {
            var mesh = new Mesh { name = "TwinSurface" };
            var v3 = new Vector3[verts.Length];
            for (int i = 0; i < verts.Length; i++) v3[i] = EpToUnity(verts[i]);

            // Outset windows along face normal so they sit proud of the wall (IDF verts are coplanar).
            if (IsWindow(surfaceType) && windowOutsetM > 0f && v3.Length >= 3)
            {
                var n = Vector3.Cross(v3[1] - v3[0], v3[2] - v3[0]).normalized;
                for (int i = 0; i < v3.Length; i++) v3[i] += n * windowOutsetM;
            }

            mesh.vertices = v3;
            if (verts.Length == 4)
            {
                // Double-sided for glass visibility from outside/inside
                if (IsWindow(surfaceType))
                    mesh.triangles = new[] { 0, 1, 2, 0, 2, 3, 0, 2, 1, 0, 3, 2 };
                else
                    mesh.triangles = new[] { 0, 1, 2, 0, 2, 3 };
            }
            else
            {
                var tris = new List<int>();
                for (int i = 1; i < verts.Length - 1; i++)
                {
                    tris.Add(0);
                    tris.Add(i);
                    tris.Add(i + 1);
                    if (IsWindow(surfaceType))
                    {
                        tris.Add(0);
                        tris.Add(i + 1);
                        tris.Add(i);
                    }
                }
                mesh.triangles = tris.ToArray();
            }
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Build Massing From StreamingAssets")]
        public static void MenuBuild()
        {
            var existing = FindAnyObjectByType<TwinGeometryBuilder>();
            if (existing == null)
            {
                var go = new GameObject("TwinGeometryBuilder");
                existing = go.AddComponent<TwinGeometryBuilder>();
            }
            existing.BuildFromStreamingAssets();
            EditorUtility.SetDirty(existing);
        }
#endif
    }
}
