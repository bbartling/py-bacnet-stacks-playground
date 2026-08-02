using UnityEngine;
using UnityEngine.Rendering;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>URP-safe translucent glass setup (avoids opaque-black panes).</summary>
    public static class GlassUtil
    {
        static Shader FindUrpLit()
        {
            // Prefer URP Lit; never return a null shader into new Material(...) on WebGL.
            return Shader.Find("Universal Render Pipeline/Lit")
                   ?? Shader.Find("Universal Render Pipeline/Simple Lit")
                   ?? Shader.Find("Sprites/Default")
                   ?? Shader.Find("UI/Default")
                   ?? Shader.Find("Standard");
        }

        public static Material MakeGlass(Color tint)
        {
            var shader = FindUrpLit();
            if (shader == null)
            {
                Debug.LogError("GlassUtil: no shader available (URP Lit stripped?). Skipping glass material.");
                return null;
            }
            var m = new Material(shader);
            ApplyTransparent(m, tint);
            return m;
        }

        public static void ApplyTransparent(Material m, Color tint)
        {
            if (m == null) return;
            if (tint.a >= 0.99f) tint.a = 0.28f;

            m.color = tint;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", tint);
            if (m.HasProperty("_Color")) m.SetColor("_Color", tint);

            // URP Lit transparent surface
            if (m.HasProperty("_Surface")) m.SetFloat("_Surface", 1f); // Transparent
            if (m.HasProperty("_Blend")) m.SetFloat("_Blend", 0f); // Alpha
            if (m.HasProperty("_AlphaClip")) m.SetFloat("_AlphaClip", 0f);
            if (m.HasProperty("_SrcBlend")) m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            if (m.HasProperty("_DstBlend")) m.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
            if (m.HasProperty("_SrcBlendAlpha")) m.SetFloat("_SrcBlendAlpha", (float)BlendMode.One);
            if (m.HasProperty("_DstBlendAlpha")) m.SetFloat("_DstBlendAlpha", (float)BlendMode.OneMinusSrcAlpha);
            if (m.HasProperty("_ZWrite")) m.SetFloat("_ZWrite", 0f);
            if (m.HasProperty("_Cull")) m.SetFloat("_Cull", 0f); // off — see both sides
            if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", 0.05f);
            if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", 0.85f);
            if (m.HasProperty("_ReceiveShadows")) m.SetFloat("_ReceiveShadows", 0f);

            m.SetOverrideTag("RenderType", "Transparent");
            m.SetOverrideTag("Queue", "Transparent");
            m.renderQueue = (int)RenderQueue.Transparent; // 3000

            m.DisableKeyword("_ALPHATEST_ON");
            m.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.EnableKeyword("_ALPHABLEND_ON");
            m.EnableKeyword("_ENVIRONMENTREFLECTIONS_OFF");
        }

        /// <summary>Force all window TwinEntity renderers to translucent glass.</summary>
        public static int FixAllWindowsInScene(float alpha = 0.28f)
        {
            int n = 0;
            var tint = new Color(0.45f, 0.65f, 0.85f, alpha);
            var shared = MakeGlass(tint);
            if (shared == null) return 0;
            foreach (var te in Object.FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "window") continue;
                foreach (var r in te.GetComponentsInChildren<MeshRenderer>())
                {
                    r.sharedMaterial = shared;
                    r.shadowCastingMode = ShadowCastingMode.Off;
                    r.receiveShadows = false;
                    // Clear any opaque MPB leftover
                    r.SetPropertyBlock(null);
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
