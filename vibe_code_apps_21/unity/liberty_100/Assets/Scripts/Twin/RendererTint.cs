using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Tint renderers without instantiating materials (avoids edit-mode leaks).</summary>
    public static class RendererTint
    {
        static MaterialPropertyBlock _block;

        public static void SetColor(Renderer r, Color color, float emissionStrength = 0f)
        {
            if (r == null) return;
            if (_block == null) _block = new MaterialPropertyBlock();
            r.GetPropertyBlock(_block);
            _block.SetColor("_BaseColor", color);
            _block.SetColor("_Color", color);
            if (emissionStrength > 0f)
            {
                var e = new Color(color.r, color.g, color.b, 1f) * emissionStrength;
                _block.SetColor("_EmissionColor", e);
            }
            r.SetPropertyBlock(_block);
        }

        public static void LerpSharedColor(Renderer r, Color wash, float t)
        {
            if (r == null || r.sharedMaterial == null) return;
            var m = r.sharedMaterial;
            var baseCol = m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor") : m.color;
            var mixed = Color.Lerp(baseCol, wash, t);
            mixed.a = baseCol.a;
            SetColor(r, mixed);
        }
    }
}
