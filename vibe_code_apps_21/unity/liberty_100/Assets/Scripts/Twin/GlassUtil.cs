using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>URP-safe translucent glass setup (avoids opaque-black panes).</summary>
    public static class GlassUtil
    {
        public static Material MakeGlass(Color tint)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var m = new Material(shader);
            ApplyTransparent(m, tint);
            return m;
        }

        public static void ApplyTransparent(Material m, Color tint)
        {
            if (m == null) return;
            m.color = tint;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", tint);
            if (m.HasProperty("_Color")) m.SetColor("_Color", tint);
            if (m.HasProperty("_Surface")) m.SetFloat("_Surface", 1f);
            if (m.HasProperty("_Blend")) m.SetFloat("_Blend", 0f);
            if (m.HasProperty("_SrcBlend")) m.SetFloat("_SrcBlend", (float)UnityEngine.Rendering.BlendMode.SrcAlpha);
            if (m.HasProperty("_DstBlend")) m.SetFloat("_DstBlend", (float)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            if (m.HasProperty("_ZWrite")) m.SetFloat("_ZWrite", 0f);
            if (m.HasProperty("_Cull")) m.SetFloat("_Cull", 0f); // off — see both sides
            if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", 0.05f);
            if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", 0.9f);
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.DisableKeyword("_ALPHATEST_ON");
            m.EnableKeyword("_ALPHABLEND_ON");
            m.renderQueue = 3000;
            m.SetOverrideTag("RenderType", "Transparent");
        }

        /// <summary>Force all window TwinEntity renderers to translucent glass.</summary>
        public static int FixAllWindowsInScene(float alpha = 0.28f)
        {
            int n = 0;
            var tint = new Color(0.45f, 0.65f, 0.85f, alpha);
            var shared = MakeGlass(tint);
            foreach (var te in Object.FindObjectsByType<TwinEntity>(FindObjectsSortMode.None))
            {
                if (te.entityType != "window") continue;
                foreach (var r in te.GetComponentsInChildren<MeshRenderer>())
                {
                    r.sharedMaterial = shared;
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    n++;
                }
            }
            return n;
        }

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Fix Window Glass Transparency")]
        public static void MenuFix()
        {
            int n = FixAllWindowsInScene();
            Debug.Log($"GlassUtil: fixed {n} window renderers");
        }
#endif
    }
}
