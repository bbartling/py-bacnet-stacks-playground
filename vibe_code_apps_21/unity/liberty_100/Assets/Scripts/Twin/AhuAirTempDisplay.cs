using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>DEMO AHU air temperatures with separate world labels (leave / mix / return / OA).</summary>
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

        /// <summary>World-space vertical gap between stacked AHU readouts.</summary>
        public float labelStackPitch = 1.15f;

        public void BuildSeparateLabels(Transform parent, float ahuHeight)
        {
            ClearChildLabels(parent);
            // Column off the front face so strings do not pile on the cabinet
            float x = isAhu2 ? 3.4f : -3.4f;
            float z = -2.0f;
            float y0 = ahuHeight + 0.4f;

            oaLabel = MakeLabel(parent, "Label_OA", new Vector3(x, y0 + labelStackPitch * 3f, z),
                new Color(0.45f, 0.85f, 0.55f));
            mixLabel = MakeLabel(parent, "Label_Mix", new Vector3(x, y0 + labelStackPitch * 2f, z),
                new Color(0.9f, 0.9f, 0.75f));
            returnLabel = MakeLabel(parent, "Label_Return", new Vector3(x, y0 + labelStackPitch * 1f, z),
                new Color(1f, 0.65f, 0.45f));
            leaveLabel = MakeLabel(parent, "Label_Leave", new Vector3(x, y0, z),
                new Color(0.45f, 0.7f, 1f));
            RefreshLabel();
        }

        /// <summary>Re-space labels already on this AHU (Play / Editor) without full AHU rebuild.</summary>
        public void RelayoutLabels()
        {
            float x = isAhu2 ? 3.4f : -3.4f;
            float z = -2.0f;
            float y0 = 2.8f;
            // Prefer current leave label height as base if present
            if (leaveLabel != null)
                y0 = leaveLabel.transform.localPosition.y;
            else if (mixLabel != null)
                y0 = mixLabel.transform.localPosition.y - labelStackPitch * 2f;

            Place(oaLabel, new Vector3(x, y0 + labelStackPitch * 3f, z));
            Place(mixLabel, new Vector3(x, y0 + labelStackPitch * 2f, z));
            Place(returnLabel, new Vector3(x, y0 + labelStackPitch * 1f, z));
            Place(leaveLabel, new Vector3(x, y0, z));

            Style(oaLabel);
            Style(mixLabel);
            Style(returnLabel);
            Style(leaveLabel);
            if (leaveLabel != null) leaveLabel.lineSpacing = 1.55f;
            RefreshLabel();
        }

        static void Place(TextMesh tm, Vector3 localPos)
        {
            if (tm == null) return;
            tm.transform.localPosition = localPos;
        }

        static void Style(TextMesh tm)
        {
            if (tm == null) return;
            tm.characterSize = 0.13f;
            tm.fontSize = 48;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.lineSpacing = 1.45f;
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
            RefreshLabel();
        }

        public void RefreshLabel()
        {
            if (oaLabel != null)
                oaLabel.text = $"OA\n{TempUnits.Format(oatC)}";
            if (leaveLabel != null)
                leaveLabel.text = $"{airLoopName}\nSA {TempUnits.Format(leaveC)}";
            if (mixLabel != null)
                mixLabel.text = $"Mix\n{TempUnits.Format(mixC)}";
            if (returnLabel != null)
                returnLabel.text = $"RA\n{TempUnits.Format(returnC)}";
            if (label != null && leaveLabel == null)
                label.text = $"{airLoopName}\nDAT {TempUnits.Format(leaveC)}\nMix {TempUnits.Format(mixC)}\nRAT {TempUnits.Format(returnC)}";
        }

        void Start()
        {
            // Fix crowded labels from older spawns
            if (leaveLabel != null || mixLabel != null)
                RelayoutLabels();
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

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Fix AHU Temp Label Spacing")]
        public static void MenuFixAhuLabels()
        {
            int n = 0;
            foreach (var a in Object.FindObjectsByType<AhuAirTempDisplay>())
            {
                a.labelStackPitch = 1.15f;
                // Rebuild if missing any of the four
                if (a.oaLabel == null || a.leaveLabel == null || a.mixLabel == null || a.returnLabel == null)
                    a.BuildSeparateLabels(a.transform, 2.4f);
                else
                    a.RelayoutLabels();
                n++;
            }
            Debug.Log($"AhuAirTempDisplay: relayout {n} AHU label stacks");
        }
#endif
    }
}
