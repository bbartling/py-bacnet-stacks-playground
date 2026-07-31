using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Spins AHU supply + return SpinPivots around local Y (airflow axis).
    /// Animates mix damper blades. Load drops hard on chiller_off / hvac_off.
    /// </summary>
    public class AhuFanSpin : MonoBehaviour
    {
        public Transform fanWheel;
        public Transform returnFanWheel;
        public Transform damperRoot;
        public float baseRpm = 90f;
        public float loadRpmBoost = 140f;
        [Range(0f, 1.5f)] public float loadFactor = 0.6f;
        public string airLoopName = "VAV Sys 1";
        public string ahuType = "VAV_CHW";
        [Range(0f, 1f)] public float damperOpen = 0.55f;

        void Update()
        {
            float rpm = baseRpm + loadRpmBoost * Mathf.Clamp01(loadFactor);
            float deg = rpm * 6f * Time.deltaTime;
            SpinLocalY(fanWheel, deg);
            SpinLocalY(returnFanWheel, deg * 0.85f);
            AnimateDampers();
        }

        static void SpinLocalY(Transform t, float degrees)
        {
            if (t == null) return;
            t.Rotate(0f, degrees, 0f, Space.Self);
        }

        void AnimateDampers()
        {
            if (damperRoot == null) return;
            float angle = Mathf.Lerp(5f, 55f, damperOpen);
            foreach (Transform bank in damperRoot)
            {
                foreach (Transform blade in bank)
                {
                    var e = blade.localEulerAngles;
                    blade.localRotation = Quaternion.Euler(e.x, e.y, angle);
                }
            }
        }

        public void SetLoadFromStrategy(string strategyId, float facilityKw)
        {
            float t = Mathf.InverseLerp(150f, 320f, facilityKw);
            float s = 0.7f;
            if (!string.IsNullOrEmpty(strategyId))
            {
                if (strategyId.Contains("chiller") || strategyId.Contains("hvac_off")) s = 0.08f;
                else if (strategyId.Contains("precool")) s = 1.1f;
                else if (strategyId.Contains("deadband") || strategyId.Contains("loadshed")) s = 0.55f;
            }
            loadFactor = Mathf.Clamp(t * s, 0.02f, 1.4f);
            damperOpen = strategyId != null && strategyId.Contains("hvac_off") ? 0.1f : 0.55f;
        }
    }
}
