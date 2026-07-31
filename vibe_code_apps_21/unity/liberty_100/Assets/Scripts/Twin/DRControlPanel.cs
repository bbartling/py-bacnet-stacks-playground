using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>On-screen DR scrubbers → Flask → zone tint + provenance HUD.</summary>
    public class DRControlPanel : MonoBehaviour
    {
        public DemandApiClient api;
        public float oatC = 32f;
        public float rhPct = 55f;
        public int hourEnding = 15;
        public float precoolF;
        public float relaxClgF;
        public int strategyIndex;
        public bool panelOpen = true;

        static readonly string[] Strategies =
        {
            "baseline", "precool_shift", "deadband_10f", "chiller_off",
            "loadshed_p5f", "hvac_off", "precool_chiller_off"
        };

        string _status = "Idle — start Flask on :5050";
        float _lastKw = float.NaN;
        string _provenance = "";
        bool _busy;

        void Awake()
        {
            if (api == null) api = GetComponent<DemandApiClient>() ?? gameObject.AddComponent<DemandApiClient>();
        }

        void OnGUI()
        {
            const float w = 340f;
            float x = Screen.width - w - 12f;
            float y = 12f;
            GUI.Box(new Rect(x, y, w, panelOpen ? 360f : 36f), "Liberty 100 — DR Twin");
            if (GUI.Button(new Rect(x + w - 28f, y + 4f, 24f, 24f), panelOpen ? "–" : "+"))
                panelOpen = !panelOpen;
            if (!panelOpen) return;

            float row = y + 36f;
            GUI.Label(new Rect(x + 12f, row, 120f, 20f), $"OAT °C {oatC:0.0}");
            oatC = GUI.HorizontalSlider(new Rect(x + 130f, row + 4f, 190f, 20f), oatC, 10f, 42f);
            row += 28f;
            GUI.Label(new Rect(x + 12f, row, 120f, 20f), $"RH % {rhPct:0.0}");
            rhPct = GUI.HorizontalSlider(new Rect(x + 130f, row + 4f, 190f, 20f), rhPct, 20f, 95f);
            row += 28f;
            GUI.Label(new Rect(x + 12f, row, 120f, 20f), $"Hour {hourEnding}");
            hourEnding = Mathf.RoundToInt(GUI.HorizontalSlider(new Rect(x + 130f, row + 4f, 190f, 20f), hourEnding, 1, 24));
            row += 28f;
            GUI.Label(new Rect(x + 12f, row, 120f, 20f), $"Precool °F {precoolF:0.0}");
            precoolF = GUI.HorizontalSlider(new Rect(x + 130f, row + 4f, 190f, 20f), precoolF, 0f, 6f);
            row += 28f;
            GUI.Label(new Rect(x + 12f, row, 120f, 20f), $"Relax clg °F {relaxClgF:0.0}");
            relaxClgF = GUI.HorizontalSlider(new Rect(x + 130f, row + 4f, 190f, 20f), relaxClgF, 0f, 10f);
            row += 28f;
            GUI.Label(new Rect(x + 12f, row, w - 24f, 20f), $"Strategy: {Strategies[strategyIndex]}");
            row += 22f;
            if (GUI.Button(new Rect(x + 12f, row, 150f, 24f), "◀ Prev"))
                strategyIndex = (strategyIndex + Strategies.Length - 1) % Strategies.Length;
            if (GUI.Button(new Rect(x + 170f, row, 150f, 24f), "Next ▶"))
                strategyIndex = (strategyIndex + 1) % Strategies.Length;
            row += 32f;
            GUI.enabled = !_busy;
            if (GUI.Button(new Rect(x + 12f, row, w - 24f, 28f), _busy ? "Predicting…" : "Predict facility kW"))
                StartCoroutine(RunPredict());
            GUI.enabled = true;
            row += 36f;
            GUI.Label(new Rect(x + 12f, row, w - 24f, 20f),
                float.IsNaN(_lastKw) ? "kW: —" : $"Predicted facility kW: {_lastKw:0.0}");
            row += 22f;
            GUI.Label(new Rect(x + 12f, row, w - 24f, 60f), _status + "\n" + _provenance);
        }

        System.Collections.IEnumerator RunPredict()
        {
            _busy = true;
            var sid = Strategies[strategyIndex];
            var phase = sid == "baseline" ? "baseline" :
                (sid.Contains("precool") ? "precool" : (sid.Contains("chiller") || sid.Contains("hvac") ? "shed" : "relax"));
            var req = new DemandPredictRequest
            {
                hour_ending = hourEnding,
                oat_c = oatC,
                rh_pct = rhPct,
                precool_f = precoolF,
                relax_clg_f = relaxClgF,
                strategy_id = sid,
                phase = phase,
                in_dr_window = sid == "baseline" ? 0 : 1,
                oat_lag1 = oatC - 0.5f
            };
            yield return api.Predict(req,
                ok =>
                {
                    _lastKw = ok.facility_kw;
                    _status = $"{ok.model_id} [{ok.model_status}]";
                    _provenance = ok.provenance != null
                        ? $"{ok.provenance.source} / {ok.provenance.engine}"
                        : "";
                    ApplyZoneTint(ok.facility_kw);
                },
                err => { _status = "API error: " + err; });
            _busy = false;
        }

        void ApplyZoneTint(float kw)
        {
            // Map ~100–350 kW to green→amber→red for massing renderers
            float t = Mathf.InverseLerp(120f, 320f, kw);
            var col = Color.Lerp(new Color(0.35f, 0.75f, 0.4f), new Color(0.9f, 0.25f, 0.2f), t);
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone" && te.entityType != "surface") continue;
                foreach (var r in te.GetComponentsInChildren<MeshRenderer>())
                {
                    if (r.sharedMaterial == null) continue;
                    var m = new Material(r.sharedMaterial);
                    m.color = Color.Lerp(m.color, col, 0.55f);
                    r.material = m;
                }
            }
        }
    }
}
