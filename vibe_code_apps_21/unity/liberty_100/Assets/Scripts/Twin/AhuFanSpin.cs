using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Silly spinning fan wheel for VAV AHU DEMO proxies (IDF Fan:VariableVolume).</summary>
    public class AhuFanSpin : MonoBehaviour
    {
        public Transform fanWheel;
        public float baseRpm = 90f;
        public float loadRpmBoost = 140f;
        [Range(0f, 1.5f)] public float loadFactor = 0.6f;
        public string airLoopName = "VAV Sys 1";
        public string ahuType = "VAV_CHW";

        void Update()
        {
            if (fanWheel == null) return;
            float rpm = baseRpm + loadRpmBoost * Mathf.Clamp01(loadFactor);
            SpinUtil.SpinFanDisk(fanWheel, rpm * 6f * Time.deltaTime);
        }

        public void SetLoadFromStrategy(string strategyId, float facilityKw)
        {
            float t = Mathf.InverseLerp(150f, 320f, facilityKw);
            float s = 0.7f;
            if (!string.IsNullOrEmpty(strategyId))
            {
                if (strategyId.Contains("chiller") || strategyId.Contains("hvac_off")) s = 0.15f;
                else if (strategyId.Contains("precool")) s = 1.1f;
                else if (strategyId.Contains("deadband") || strategyId.Contains("loadshed")) s = 0.55f;
            }
            loadFactor = Mathf.Clamp(t * s, 0.05f, 1.4f);
        }
    }
}
