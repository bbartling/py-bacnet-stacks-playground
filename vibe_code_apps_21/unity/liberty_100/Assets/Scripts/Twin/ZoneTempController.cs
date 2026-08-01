using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Soft BAS-style floor/zone temperature gradients (DEMO, not live BAS).
    /// Tints windows + zone shells via MaterialPropertyBlock (no material leaks).
    /// </summary>
    public class ZoneTempController : MonoBehaviour
    {
        public float baseComfortC = 22.5f;
        public float oatBiasScale = 0.12f;
        public float floorStackBiasC = 0.35f;
        public float ahuSplitC = 0.6f;
        // Hot/cold glass wash — readable through translucent panes
        public float glowStrength = 0.55f;

        readonly Dictionary<string, float> _temps = new Dictionary<string, float>();

        static readonly Color Cool = new Color(0.35f, 0.62f, 0.98f, 0.32f);
        static readonly Color Warm = new Color(0.98f, 0.42f, 0.32f, 0.32f);

        public IReadOnlyDictionary<string, float> Temps => _temps;

        public void RefreshFromDr(float oatC, string strategyId, float precoolF, float relaxClgF)
        {
            _temps.Clear();
            float strategyBias = 0f;
            if (!string.IsNullOrEmpty(strategyId))
            {
                if (strategyId.Contains("precool")) strategyBias -= 0.8f + precoolF * 0.25f;
                if (strategyId.Contains("deadband") || strategyId.Contains("loadshed"))
                    strategyBias += 0.5f + relaxClgF * 0.15f;
                if (strategyId.Contains("chiller") || strategyId.Contains("hvac_off"))
                    strategyBias += 2.8f;
            }

            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone") continue;
                int floor = ParseFloor(te.displayName);
                bool ahu2 = te.displayName != null && te.displayName.Contains("AHU2");
                float t = baseComfortC
                    + (oatC - 24f) * oatBiasScale
                    + (floor - 1) * floorStackBiasC
                    + (ahu2 ? ahuSplitC : -ahuSplitC * 0.4f)
                    + strategyBias
                    + HashJitter(te.entityId) * 0.4f;
                _temps[te.entityId] = t;
            }

            ApplyToSensors();
            ApplyWindowGlow();
            ApplyZoneShellTint();
            ApplyAhuAirTemps(oatC, strategyId);
        }

        void ApplyAhuAirTemps(float oatC, string strategyId)
        {
            float sum = 0f;
            int n = 0;
            foreach (var kv in _temps) { sum += kv.Value; n++; }
            float avg = n > 0 ? sum / n : baseComfortC;
            foreach (var ahu in FindObjectsByType<AhuAirTempDisplay>())
                ahu.Apply(oatC, strategyId, avg);
        }

        public void ApplyDemoDefaults(float oatC = 32f)
        {
            RefreshFromDr(oatC, "baseline", 0f, 0f);
        }

        void ApplyToSensors()
        {
            foreach (var s in FindObjectsByType<ZoneTempSensor>())
            {
                if (s.zoneEntityId != null && _temps.TryGetValue(s.zoneEntityId, out var t))
                    s.SetTemp(t);
            }
        }

        void ApplyWindowGlow()
        {
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "window") continue;
                string zoneId = te.entityId;
                if (string.IsNullOrEmpty(zoneId) || !_temps.TryGetValue(zoneId, out var tempC))
                    continue;
                float u = Mathf.InverseLerp(16f, 30f, tempC);
                foreach (var r in te.GetComponentsInChildren<MeshRenderer>())
                {
                    // Preserve glass alpha from shared material (never force opaque)
                    float a = 0.32f;
                    if (r.sharedMaterial != null)
                    {
                        var baseCol = r.sharedMaterial.HasProperty("_BaseColor")
                            ? r.sharedMaterial.GetColor("_BaseColor")
                            : r.sharedMaterial.color;
                        if (baseCol.a > 0.01f && baseCol.a < 0.99f) a = Mathf.Max(baseCol.a, 0.28f);
                    }
                    var glass = Color.Lerp(Cool, Warm, u);
                    glass.a = a;
                    RendererTint.SetColor(r, glass, glowStrength);
                }
            }
        }

        void ApplyZoneShellTint()
        {
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone") continue;
                if (!_temps.TryGetValue(te.entityId, out var tempC)) continue;
                float u = Mathf.InverseLerp(16f, 30f, tempC);
                var wash = Color.Lerp(
                    new Color(0.45f, 0.62f, 0.92f, 1f),
                    new Color(0.92f, 0.45f, 0.38f, 1f),
                    u);
                foreach (var r in te.GetComponentsInChildren<MeshRenderer>())
                {
                    var child = r.GetComponent<TwinEntity>();
                    if (child != null && (child.entityType == "window" || child.entityType == "sensor_proxy"))
                        continue;
                    if (r.sharedMaterial == null) continue;
                    RendererTint.LerpSharedColor(r, wash, 0.22f);
                }
            }
        }

        static int ParseFloor(string name)
        {
            if (string.IsNullOrEmpty(name)) return 1;
            var m = Regex.Match(name, @"Floor_(\d+)");
            return m.Success ? int.Parse(m.Groups[1].Value) : 1;
        }

        static float HashJitter(string id)
        {
            if (string.IsNullOrEmpty(id)) return 0f;
            unchecked
            {
                int h = 0;
                foreach (char c in id) h = h * 31 + c;
                return ((h & 0xffff) / 65535f) * 2f - 1f;
            }
        }
    }
}
