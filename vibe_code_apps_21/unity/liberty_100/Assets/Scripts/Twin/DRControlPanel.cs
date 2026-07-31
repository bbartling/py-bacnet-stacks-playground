using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>On-screen DR scrubbers → Flask → zone tint + temp gradients + provenance HUD.</summary>
    public class DRControlPanel : MonoBehaviour
    {
        public DemandApiClient api;
        public ZoneTempController tempController;
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
        GUIStyle _titleStyle;
        GUIStyle _labelStyle;
        GUIStyle _buttonStyle;
        bool _stylesReady;

        void Awake()
        {
            if (api == null) api = GetComponent<DemandApiClient>() ?? gameObject.AddComponent<DemandApiClient>();
            if (tempController == null)
                tempController = GetComponent<ZoneTempController>() ?? gameObject.AddComponent<ZoneTempController>();
        }

        void Start()
        {
            // Seed DEMO floor temps so windows/sensors look alive before first predict
            tempController.ApplyDemoDefaults(oatC);
        }

        void EnsureStyles()
        {
            if (_stylesReady) return;
            _titleStyle = new GUIStyle(GUI.skin.box)
            {
                fontSize = 22,
                fontStyle = FontStyle.Bold,
                alignment = TextAnchor.MiddleLeft,
                padding = new RectOffset(14, 14, 8, 8)
            };
            _labelStyle = new GUIStyle(GUI.skin.label) { fontSize = 16 };
            _buttonStyle = new GUIStyle(GUI.skin.button) { fontSize = 16, fixedHeight = 36 };
            _stylesReady = true;
        }

        void OnGUI()
        {
            EnsureStyles();
            const float w = 520f;
            const float rowH = 36f;
            float panelH = panelOpen ? 520f : 48f;
            float x = Screen.width - w - 16f;
            float y = 16f;

            GUI.Box(new Rect(x, y, w, panelH), "");
            GUI.Label(new Rect(x + 12f, y + 6f, w - 70f, 36f), "Liberty 100 — DR Twin Sim", _titleStyle);
            if (GUI.Button(new Rect(x + w - 44f, y + 8f, 36f, 32f), panelOpen ? "–" : "+", _buttonStyle))
                panelOpen = !panelOpen;
            if (!panelOpen) return;

            float row = y + 52f;
            float labelW = 170f;
            float sliderX = x + labelW + 8f;
            float sliderW = w - labelW - 36f;

            GUI.Label(new Rect(x + 16f, row, labelW, rowH), $"OAT °C  {oatC:0.0}", _labelStyle);
            oatC = GUI.HorizontalSlider(new Rect(sliderX, row + 12f, sliderW, 20f), oatC, 10f, 42f);
            row += rowH;

            GUI.Label(new Rect(x + 16f, row, labelW, rowH), $"RH %  {rhPct:0.0}", _labelStyle);
            rhPct = GUI.HorizontalSlider(new Rect(sliderX, row + 12f, sliderW, 20f), rhPct, 20f, 95f);
            row += rowH;

            GUI.Label(new Rect(x + 16f, row, labelW, rowH), $"Hour ending  {hourEnding}", _labelStyle);
            hourEnding = Mathf.RoundToInt(GUI.HorizontalSlider(new Rect(sliderX, row + 12f, sliderW, 20f), hourEnding, 1, 24));
            row += rowH;

            GUI.Label(new Rect(x + 16f, row, labelW, rowH), $"Precool °F  {precoolF:0.0}", _labelStyle);
            precoolF = GUI.HorizontalSlider(new Rect(sliderX, row + 12f, sliderW, 20f), precoolF, 0f, 6f);
            row += rowH;

            GUI.Label(new Rect(x + 16f, row, labelW, rowH), $"Relax clg °F  {relaxClgF:0.0}", _labelStyle);
            relaxClgF = GUI.HorizontalSlider(new Rect(sliderX, row + 12f, sliderW, 20f), relaxClgF, 0f, 10f);
            row += rowH;

            GUI.Label(new Rect(x + 16f, row, w - 32f, rowH), $"Strategy:  {Strategies[strategyIndex]}", _labelStyle);
            row += 30f;
            if (GUI.Button(new Rect(x + 16f, row, (w - 48f) * 0.5f, 40f), "◀  Prev strategy", _buttonStyle))
                strategyIndex = (strategyIndex + Strategies.Length - 1) % Strategies.Length;
            if (GUI.Button(new Rect(x + 28f + (w - 48f) * 0.5f, row, (w - 48f) * 0.5f, 40f), "Next strategy  ▶", _buttonStyle))
                strategyIndex = (strategyIndex + 1) % Strategies.Length;
            row += 52f;

            GUI.enabled = !_busy;
            if (GUI.Button(new Rect(x + 16f, row, w - 32f, 48f),
                    _busy ? "Predicting…" : "Predict facility kW  +  refresh zone temps", _buttonStyle))
                StartCoroutine(RunPredict());
            GUI.enabled = true;
            row += 58f;

            GUI.Label(new Rect(x + 16f, row, w - 32f, 28f),
                float.IsNaN(_lastKw) ? "Predicted facility kW:  —" : $"Predicted facility kW:  {_lastKw:0.0}",
                _labelStyle);
            row += 28f;
            GUI.Label(new Rect(x + 16f, row, w - 32f, 70f),
                _status + "\n" + _provenance + "\nZone °C = DEMO BAS-style (not live)", _labelStyle);
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
            // Refresh DEMO temps immediately so scrubbing feels responsive even if API lags
            tempController.RefreshFromDr(oatC, sid, precoolF, relaxClgF);
            yield return api.Predict(req,
                ok =>
                {
                    _lastKw = ok.facility_kw;
                    _status = $"{ok.model_id} [{ok.model_status}]";
                    _provenance = ok.provenance != null
                        ? $"{ok.provenance.source} / {ok.provenance.engine}"
                        : "";
                    ApplyKwWash(ok.facility_kw);
                    tempController.RefreshFromDr(oatC, sid, precoolF, relaxClgF);
                    foreach (var spin in FindObjectsByType<AhuFanSpin>())
                        spin.SetLoadFromStrategy(sid, ok.facility_kw);
                },
                err => { _status = "API error: " + err; });
            _busy = false;
        }

        void ApplyKwWash(float kw)
        {
            float t = Mathf.InverseLerp(120f, 320f, kw);
            var col = Color.Lerp(new Color(0.35f, 0.75f, 0.4f), new Color(0.9f, 0.25f, 0.2f), t);
            foreach (var te in FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone") continue;
                foreach (var r in te.GetComponentsInChildren<MeshRenderer>())
                {
                    var child = r.GetComponent<TwinEntity>();
                    if (child != null && (child.entityType == "window" || child.entityType == "sensor_proxy"))
                        continue;
                    if (r.sharedMaterial == null) continue;
                    RendererTint.LerpSharedColor(r, col, 0.22f);
                }
            }
        }
    }
}
