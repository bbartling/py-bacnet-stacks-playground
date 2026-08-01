using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// DEMO zone temperature sensor — individual BAS-style readout for drone flythrough.
    /// Label is only visible when camera has LOS through open air or a window TwinEntity.
    /// </summary>
    public class ZoneTempSensor : MonoBehaviour
    {
        public string zoneEntityId;
        public string floorLabel;
        public float tempC = 22f;
        public TextMesh label;
        public Renderer bulb;
        public float occlusionInterval = 0.08f;

        static readonly Color Cool = new Color(0.25f, 0.45f, 0.95f, 1f);
        static readonly Color Neutral = new Color(0.85f, 0.85f, 0.75f, 1f);
        static readonly Color Warm = new Color(0.95f, 0.28f, 0.22f, 1f);

        float _occTimer;
        bool _visible = true;
        Collider _selfCol;
        MeshRenderer _labelRenderer;

        void Awake()
        {
            _selfCol = GetComponent<Collider>();
            if (label != null)
                _labelRenderer = label.GetComponent<MeshRenderer>();
        }

        public void SetTemp(float c)
        {
            tempC = c;
            ApplyVisual();
        }

        public void ApplyVisual()
        {
            float t = Mathf.InverseLerp(18f, 28f, tempC);
            var col = t < 0.5f
                ? Color.Lerp(Cool, Neutral, t * 2f)
                : Color.Lerp(Neutral, Warm, (t - 0.5f) * 2f);
            if (bulb != null)
                RendererTint.SetColor(bulb, col, 0.55f);
            if (label != null)
                label.text = $"{floorLabel}\n{TempUnits.Format(tempC)}";
            ApplyVisibility(_visible);
        }

        void LateUpdate()
        {
            if (label == null) return;
            var cam = Camera.main;
            if (cam == null) return;

            label.transform.rotation = Quaternion.LookRotation(label.transform.position - cam.transform.position);

            _occTimer -= Time.unscaledDeltaTime;
            if (_occTimer > 0f) return;
            _occTimer = occlusionInterval;

            bool show = HasLineOfSight(cam.transform.position, label.transform.position);
            if (show != _visible)
            {
                _visible = show;
                ApplyVisibility(_visible);
            }
        }

        void ApplyVisibility(bool show)
        {
            if (label != null)
            {
                var c = label.color;
                c.a = show ? 1f : 0f;
                label.color = c;
                if (_labelRenderer != null)
                    _labelRenderer.enabled = show;
                label.gameObject.SetActive(show);
            }
            if (bulb != null)
            {
                // Dim bulb when occluded so it doesn't read through walls either
                var cols = bulb.GetComponent<MeshRenderer>();
                if (cols != null)
                {
                    var block = new MaterialPropertyBlock();
                    cols.GetPropertyBlock(block);
                    var baseCol = block.GetColor("_BaseColor");
                    if (baseCol.a <= 0f && cols.sharedMaterial != null)
                        baseCol = cols.sharedMaterial.HasProperty("_BaseColor")
                            ? cols.sharedMaterial.GetColor("_BaseColor")
                            : cols.sharedMaterial.color;
                    baseCol.a = show ? 1f : 0.15f;
                    block.SetColor("_BaseColor", baseCol);
                    block.SetColor("_Color", baseCol);
                    cols.SetPropertyBlock(block);
                }
            }
        }

        bool HasLineOfSight(Vector3 from, Vector3 to)
        {
            Vector3 delta = to - from;
            float dist = delta.magnitude;
            if (dist < 0.05f) return true;
            Vector3 dir = delta / dist;

            var hits = Physics.RaycastAll(from, dir, dist, ~0, QueryTriggerInteraction.Ignore);
            if (hits == null || hits.Length == 0) return true;

            System.Array.Sort(hits, (a, b) => a.distance.CompareTo(b.distance));
            foreach (var hit in hits)
            {
                if (hit.collider == null) continue;
                if (_selfCol != null && (hit.collider == _selfCol || hit.collider.transform.IsChildOf(transform)))
                    continue;
                if (hit.collider.transform.IsChildOf(transform) || hit.collider.transform == transform)
                    continue;

                // Stop just short of the sensor itself
                if (hit.distance > dist - 0.12f)
                    continue;

                var te = hit.collider.GetComponentInParent<TwinEntity>();
                if (te != null && te.entityType == "window")
                    return true; // looking through glazing

                // Opaque massing / wall / anything else blocks
                return false;
            }
            return true;
        }
    }
}
