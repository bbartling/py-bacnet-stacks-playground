using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>DEMO AHU air temperatures with separate world labels (leave / mix / return).</summary>
    public class AhuAirTempDisplay : MonoBehaviour
    {
        public string airLoopName = "VAV Sys 1";
        public bool isAhu2;
        public float leaveC = 13.5f;
        public float mixC = 24.0f;
        public float returnC = 25.5f;

        public TextMesh leaveLabel;
        public TextMesh mixLabel;
        public TextMesh returnLabel;
        public TextMesh oaLabel;
        public float oatC = 32f;

        // Legacy single-label support
        public TextMesh label;

        public void BuildSeparateLabels(Transform parent, float ahuHeight)
        {
            oaLabel = MakeLabel(parent, "Label_OA", new Vector3(-2.2f, ahuHeight + 0.35f, -1.4f), new Color(0.45f, 0.85f, 0.55f));
            leaveLabel = MakeLabel(parent, "Label_Leave", new Vector3(1.8f, ahuHeight + 0.55f, -1.4f), new Color(0.45f, 0.7f, 1f));
            mixLabel = MakeLabel(parent, "Label_Mix", new Vector3(-0.2f, ahuHeight + 0.95f, -1.4f), new Color(0.9f, 0.9f, 0.75f));
            returnLabel = MakeLabel(parent, "Label_Return", new Vector3(-1.4f, ahuHeight + 0.35f, -1.4f), new Color(1f, 0.65f, 0.45f));
            RefreshLabel();
        }

        static TextMesh MakeLabel(Transform parent, string name, Vector3 localPos, Color col)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var tm = go.AddComponent<TextMesh>();
            tm.characterSize = 0.11f;
            tm.fontSize = 42;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = col;
            return tm;
        }

        public void Apply(float oatC, string strategyId, float zoneAvgC)
        {
            float dat = 12.5f + (oatC - 28f) * 0.08f;
            if (!string.IsNullOrEmpty(strategyId))
            {
                if (strategyId.Contains("precool")) dat -= 1.2f;
                if (strategyId.Contains("chiller") || strategyId.Contains("hvac_off")) dat += 6f;
                if (strategyId.Contains("deadband") || strategyId.Contains("loadshed")) dat += 1.5f;
            }
            this.oatC = oatC;
            leaveC = dat + (isAhu2 ? 0.3f : 0f);
            returnC = zoneAvgC + 0.8f + (isAhu2 ? 0.2f : 0f);
            float oa = 0.22f + Mathf.Clamp01((oatC - 10f) / 40f) * 0.1f;
            mixC = oa * oatC + (1f - oa) * returnC;
            RefreshLabel();
        }

        public void RefreshLabel()
        {
            if (oaLabel != null)
                oaLabel.text = $"OA {TempUnits.Format(oatC)}";
            if (leaveLabel != null)
                leaveLabel.text = $"{airLoopName}\nLeave {TempUnits.Format(leaveC)}";
            if (mixLabel != null)
                mixLabel.text = $"Mix {TempUnits.Format(mixC)}";
            if (returnLabel != null)
                returnLabel.text = $"Return {TempUnits.Format(returnC)}";
            if (label != null && leaveLabel == null)
                label.text = $"{airLoopName}\nDAT {TempUnits.Format(leaveC)}\nMix {TempUnits.Format(mixC)}\nRAT {TempUnits.Format(returnC)}";
        }

        void LateUpdate()
        {
            Face(oaLabel);
            Face(leaveLabel);
            Face(mixLabel);
            Face(returnLabel);
            Face(label);
        }

        static void Face(TextMesh tm)
        {
            if (tm == null) return;
            var cam = Camera.main;
            if (cam == null) return;
            tm.transform.rotation = Quaternion.LookRotation(tm.transform.position - cam.transform.position);
        }
    }
}
