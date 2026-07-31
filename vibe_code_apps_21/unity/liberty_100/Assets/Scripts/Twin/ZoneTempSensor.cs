using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>DEMO zone temperature sensor — BAS-style readout for drone flythrough.</summary>
    public class ZoneTempSensor : MonoBehaviour
    {
        public string zoneEntityId;
        public string floorLabel;
        public float tempC = 22f;
        public TextMesh label;
        public Renderer bulb;

        static readonly Color Cool = new Color(0.25f, 0.45f, 0.95f, 1f);
        static readonly Color Neutral = new Color(0.85f, 0.85f, 0.75f, 1f);
        static readonly Color Warm = new Color(0.95f, 0.28f, 0.22f, 1f);

        public void SetTemp(float c)
        {
            tempC = c;
            ApplyVisual();
        }

        public void ApplyVisual()
        {
            // Comfort band ~20–24 °C; map 18→28 for soft BAS palette
            float t = Mathf.InverseLerp(18f, 28f, tempC);
            var col = t < 0.5f
                ? Color.Lerp(Cool, Neutral, t * 2f)
                : Color.Lerp(Neutral, Warm, (t - 0.5f) * 2f);
            if (bulb != null)
                RendererTint.SetColor(bulb, col, 0.55f);
            if (label != null)
                label.text = $"{floorLabel}\n{TempUnits.Format(tempC)}";
        }

        void LateUpdate()
        {
            if (label == null) return;
            var cam = Camera.main;
            if (cam == null) return;
            label.transform.rotation = Quaternion.LookRotation(label.transform.position - cam.transform.position);
        }
    }
}
