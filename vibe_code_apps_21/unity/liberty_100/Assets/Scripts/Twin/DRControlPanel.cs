using System.Collections;
using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// DR scrubbers + timed 2-hour event playback (wall clock 5 min / 1 min / 30 s).
    /// Drives Flask predict, zone temps, AHU fans, and plant (chiller/tower) visuals/audio.
    /// </summary>
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
        /// <summary>0 = 5 min, 1 = 1 min, 2 = 30 s wall-clock for a 2-hour DR window.</summary>
        public int playbackDurationIndex = 1;

        static readonly string[] Strategies =
        {
            "baseline", "precool_shift", "deadband_10f", "chiller_off",
            "loadshed_p5f", "hvac_off", "precool_chiller_off"
        };

        static readonly string[] PlaybackLabels = { "5 min", "1 min", "30 sec" };
        static readonly float[] PlaybackSeconds = { 300f, 60f, 30f };
        const float SimWindowHours = 2f;

        string _status = "Idle — start Flask on :5050";
        float _lastKw = float.NaN;
        string _provenance = "";
        bool _busy;
        bool _eventRunning;
        float _simHourProgress; // 0..2 hours into event
        Coroutine _eventCo;
        GUIStyle _titleStyle;
        GUIStyle _labelStyle;
        GUIStyle _buttonStyle;
        bool _stylesReady;

        void Awake()
        {
            if (api == null) api = GetComponent<DemandApiClient>() ?? gameObject.AddComponent<DemandApiClient>();
            if (tempController == null)
                tempController = GetComponent<ZoneTempController>() ?? gameObject.AddComponent<ZoneTempController>();
            MachineAudioHub.Ensure();
        }

        void Start()
        {
            tempController.ApplyDemoDefaults(oatC);
            var plant = FindAnyObjectByType<PlantVisualController>();
            if (plant != null) plant.ApplyStrategy("baseline", 200f);
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
            if (TwinMainMenu.Instance != null && TwinMainMenu.Instance.IsPaused) return;
            EnsureStyles();
            const float w = 540f;
            const float rowH = 36f;
            float panelH = panelOpen ? 640f : 48f;
            float x = Screen.width - w - 16f;
            float y = 16f;

            GUI.Box(new Rect(x, y, w, panelH), "");
            GUI.Label(new Rect(x + 12f, y + 6f, w - 70f, 36f), "Liberty 100 — DR Twin Sim", _titleStyle);
            if (GUI.Button(new Rect(x + w - 44f, y + 8f, 36f, 32f), panelOpen ? "–" : "+", _buttonStyle))
                panelOpen = !panelOpen;
            if (!panelOpen) return;

            float row = y + 52f;
            float labelW = 180f;
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

            GUI.Label(new Rect(x + 16f, row, w - 32f, rowH),
                $"2-hr event plays in:  {PlaybackLabels[playbackDurationIndex]}", _labelStyle);
            row += 28f;
            float btnW = (w - 56f) / 3f;
            for (int i = 0; i < 3; i++)
            {
                GUI.enabled = !_eventRunning;
                if (GUI.Button(new Rect(x + 16f + i * (btnW + 8f), row, btnW, 36f), PlaybackLabels[i], _buttonStyle))
                    playbackDurationIndex = i;
                GUI.enabled = true;
            }
            row += 48f;

            GUI.enabled = !_busy && !_eventRunning;
            if (GUI.Button(new Rect(x + 16f, row, w - 32f, 44f),
                    "Predict once  +  refresh temps", _buttonStyle))
                StartCoroutine(RunPredictOnce());
            GUI.enabled = true;
            row += 52f;

            GUI.enabled = !_busy;
            if (!_eventRunning)
            {
                if (GUI.Button(new Rect(x + 16f, row, w - 32f, 48f),
                        $"Run DR Event ({PlaybackLabels[playbackDurationIndex]})", _buttonStyle))
                {
                    if (_eventCo != null) StopCoroutine(_eventCo);
                    _eventCo = StartCoroutine(RunDrEvent());
                }
            }
            else
            {
                if (GUI.Button(new Rect(x + 16f, row, w - 32f, 48f), "Stop DR Event", _buttonStyle))
                    StopDrEvent();
            }
            GUI.enabled = true;
            row += 56f;

            if (_eventRunning)
            {
                float pct = _simHourProgress / SimWindowHours;
                GUI.Label(new Rect(x + 16f, row, w - 32f, 28f),
                    $"Event progress: {_simHourProgress:0.00} / {SimWindowHours:0} h  ({pct * 100f:0}%)", _labelStyle);
                row += 28f;
            }

            GUI.Label(new Rect(x + 16f, row, w - 32f, 28f),
                float.IsNaN(_lastKw) ? "Predicted facility kW:  —" : $"Predicted facility kW:  {_lastKw:0.0}",
                _labelStyle);
            row += 28f;
            GUI.Label(new Rect(x + 16f, row, w - 32f, 70f),
                _status + "\n" + _provenance + "\nZone °C = DEMO BAS-style (not live E+)", _labelStyle);
        }

        void StopDrEvent()
        {
            _eventRunning = false;
            if (_eventCo != null)
            {
                StopCoroutine(_eventCo);
                _eventCo = null;
            }
            _status = "DR event stopped";
        }

        IEnumerator RunDrEvent()
        {
            _eventRunning = true;
            _simHourProgress = 0f;
            float wallSec = PlaybackSeconds[Mathf.Clamp(playbackDurationIndex, 0, PlaybackSeconds.Length - 1)];
            float simHoursPerSec = SimWindowHours / wallSec;
            int startHour = hourEnding;
            float tickAccum = 0f;
            const float predictEveryWallSec = 2.5f;

            _status = $"Running 2-hr DR in {PlaybackLabels[playbackDurationIndex]}…";
            yield return RunPredictAtHour(startHour);

            while (_simHourProgress < SimWindowHours - 0.001f)
            {
                float dt = Time.unscaledDeltaTime;
                _simHourProgress = Mathf.Min(SimWindowHours, _simHourProgress + simHoursPerSec * dt);
                int he = ((startHour - 1 + Mathf.FloorToInt(_simHourProgress)) % 24) + 1;
                hourEnding = he;
                tickAccum += dt;
                if (tickAccum >= predictEveryWallSec)
                {
                    tickAccum = 0f;
                    yield return RunPredictAtHour(he);
                }
                // Soft temp drift between predicts
                tempController.RefreshFromDr(oatC, Strategies[strategyIndex], precoolF, relaxClgF);
                yield return null;
            }

            yield return RunPredictAtHour(((startHour - 1 + Mathf.FloorToInt(SimWindowHours)) % 24) + 1);
            _eventRunning = false;
            _eventCo = null;
            _status = "DR event complete";
        }

        IEnumerator RunPredictOnce()
        {
            yield return RunPredictAtHour(hourEnding);
        }

        IEnumerator RunPredictAtHour(int he)
        {
            _busy = true;
            var sid = Strategies[strategyIndex];
            var phase = sid == "baseline" ? "baseline" :
                (sid.Contains("precool") ? "precool" : (sid.Contains("chiller") || sid.Contains("hvac") ? "shed" : "relax"));
            var req = new DemandPredictRequest
            {
                hour_ending = he,
                oat_c = oatC,
                rh_pct = rhPct,
                precool_f = precoolF,
                relax_clg_f = relaxClgF,
                strategy_id = sid,
                phase = phase,
                in_dr_window = sid == "baseline" ? 0 : 1,
                oat_lag1 = oatC - 0.5f
            };
            tempController.RefreshFromDr(oatC, sid, precoolF, relaxClgF);
            ApplyPlant(sid, float.IsNaN(_lastKw) ? 200f : _lastKw);

            bool done = false;
            yield return api.Predict(req,
                ok =>
                {
                    _lastKw = ok.facility_kw;
                    _status = $"{ok.model_id} [{ok.model_status}]  h={he}";
                    _provenance = ok.provenance != null
                        ? $"{ok.provenance.source} / {ok.provenance.engine}"
                        : "";
                    ApplyKwWash(ok.facility_kw);
                    tempController.RefreshFromDr(oatC, sid, precoolF, relaxClgF);
                    ApplyPlant(sid, ok.facility_kw);
                    done = true;
                },
                err =>
                {
                    _status = "API error: " + err;
                    ApplyPlant(sid, float.IsNaN(_lastKw) ? 180f : _lastKw);
                    done = true;
                });
            while (!done) yield return null;
            _busy = false;
        }

        void ApplyPlant(string sid, float kw)
        {
            foreach (var plant in FindObjectsByType<PlantVisualController>())
                plant.ApplyStrategy(sid, kw);
            foreach (var spin in FindObjectsByType<AhuFanSpin>())
                spin.SetLoadFromStrategy(sid, kw);
            var audio = MachineAudioHub.Ensure();
            bool off = sid != null && (sid.Contains("chiller") || sid.Contains("hvac_off"));
            audio.SetAhuLoad(off ? 0.05f : Mathf.InverseLerp(120f, 320f, kw));
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
