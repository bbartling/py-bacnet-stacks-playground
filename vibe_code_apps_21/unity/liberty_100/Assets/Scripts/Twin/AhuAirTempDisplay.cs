using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>DEMO AHU air temperatures: leaving / mixed / return (°C).</summary>
    public class AhuAirTempDisplay : MonoBehaviour
    {
        public string airLoopName = "VAV Sys 1";
        public bool isAhu2;
        public float leaveC = 13.5f;
        public float mixC = 24.0f;
        public float returnC = 25.5f;
        public TextMesh label;

        public void Apply(float oatC, string strategyId, float zoneAvgC)
        {
            // Rough VAV psychrometrics toy model — DEMO only
            float dat = 12.5f + (oatC - 28f) * 0.08f;
            if (!string.IsNullOrEmpty(strategyId))
            {
                if (strategyId.Contains("precool")) dat -= 1.2f;
                if (strategyId.Contains("chiller") || strategyId.Contains("hvac_off")) dat += 6f;
                if (strategyId.Contains("deadband") || strategyId.Contains("loadshed")) dat += 1.5f;
            }
            leaveC = dat + (isAhu2 ? 0.3f : 0f);
            returnC = zoneAvgC + 0.8f + (isAhu2 ? 0.2f : 0f);
            // Mix ≈ OA fraction * OAT + (1-f) * RAT — toy OA fraction ~0.25
            float oa = 0.22f + Mathf.Clamp01((oatC - 10f) / 40f) * 0.1f;
            mixC = oa * oatC + (1f - oa) * returnC;
            RefreshLabel();
        }

        public void RefreshLabel()
        {
            if (label == null) return;
            label.text =
                $"{airLoopName}\n" +
                $"DAT/Leave  {leaveC:0.0} °C\n" +
                $"Mix        {mixC:0.0} °C\n" +
                $"Return     {returnC:0.0} °C\n" +
                "DEMO";
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
