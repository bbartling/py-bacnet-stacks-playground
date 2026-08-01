using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Roof AHU nameplate only — I/O temps live on the spreadsheet sheets.
    /// </summary>
    public class AhuAirTempDisplay : MonoBehaviour
    {
        public string airLoopName = "VAV Sys 1";
        public bool isAhu2;
        public float leaveC = 13.5f;
        public float mixC = 24.0f;
        public float returnC = 25.5f;
        public float oatC = 32f;

        public TextMesh leaveLabel;
        public TextMesh mixLabel;
        public TextMesh returnLabel;
        public TextMesh oaLabel;
        public TextMesh label;
        public float labelStackPitch = 1.15f;

        public void BuildSeparateLabels(Transform parent, float ahuHeight)
        {
            ClearChildLabels(parent);
            leaveLabel = mixLabel = returnLabel = oaLabel = null;
            float x = isAhu2 ? 3.4f : -3.4f;
            label = MakeLabel(parent, "Label_Name", new Vector3(x, ahuHeight + 0.6f, -2.0f),
                new Color(0.85f, 0.95f, 1f));
            RefreshLabel();
        }

        public void RelayoutLabels()
        {
            CollapseToNameOnly();
        }

        /// <summary>Strip OA/Mix/RA/SA stacks — keep a single equipment nameplate.</summary>
        public void CollapseToNameOnly()
        {
            ClearChildLabels(transform);
            leaveLabel = mixLabel = returnLabel = oaLabel = null;
            if (label == null)
            {
                float x = isAhu2 ? 3.4f : -3.4f;
                label = MakeLabel(transform, "Label_Name", new Vector3(x, 3.0f, -2.0f),
                    new Color(0.85f, 0.95f, 1f));
            }
            else
            {
                label.gameObject.name = "Label_Name";
                float x = isAhu2 ? 3.4f : -3.4f;
                label.transform.localPosition = new Vector3(x, 3.0f, -2.0f);
                Style(label);
            }
            RefreshLabel();
        }

        static void Style(TextMesh tm)
        {
            if (tm == null) return;
            tm.characterSize = 0.14f;
            tm.fontSize = 52;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.lineSpacing = 1.1f;
        }

        static void ClearChildLabels(Transform parent)
        {
            for (int i = parent.childCount - 1; i >= 0; i--)
            {
                var c = parent.GetChild(i);
                if (c != null && c.name.StartsWith("Label_"))
                {
                    if (Application.isPlaying) Object.Destroy(c.gameObject);
                    else Object.DestroyImmediate(c.gameObject);
                }
            }
        }

        static TextMesh MakeLabel(Transform parent, string name, Vector3 localPos, Color col)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var tm = go.AddComponent<TextMesh>();
            Style(tm);
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
            // Values feed TwinIoHub / sheets; roof plate stays name-only
            RefreshLabel();
        }

        public void RefreshLabel()
        {
            if (label != null)
                label.text = string.IsNullOrEmpty(airLoopName) ? "AHU" : airLoopName;
            if (leaveLabel != null) leaveLabel.text = "";
            if (mixLabel != null) mixLabel.text = "";
            if (returnLabel != null) returnLabel.text = "";
            if (oaLabel != null) oaLabel.text = "";
        }

        void Start()
        {
            CollapseToNameOnly();
        }

        void LateUpdate()
        {
            Face(label);
        }

        static void Face(TextMesh tm)
        {
            if (tm == null) return;
            var cam = Camera.main;
            if (cam == null) return;
            tm.transform.rotation = Quaternion.LookRotation(tm.transform.position - cam.transform.position);
        }

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/AHU Labels — Name Only")]
        public static void MenuNameOnly()
        {
            int n = 0;
            foreach (var a in Object.FindObjectsByType<AhuAirTempDisplay>())
            {
                a.CollapseToNameOnly();
                n++;
            }
            Debug.Log($"AhuAirTempDisplay: name-only on {n} AHUs");
        }
#endif
    }
}
