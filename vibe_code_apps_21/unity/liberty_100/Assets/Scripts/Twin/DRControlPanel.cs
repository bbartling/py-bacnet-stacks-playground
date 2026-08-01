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
                fontSize = 38,
                fontStyle = FontStyle.Bold,
                alignment = TextAnchor.MiddleLeft,
                padding = new RectOffset(18, 18, 12, 12)
            };
            _labelStyle = new GUIStyle(GUI.skin.label) { fontSize = 28 };
            _buttonStyle = new GUIStyle(GUI.skin.button) { fontSize = 28, fixedHeight = 56 };
            _stylesReady = true;
        }

        void OnGUI()
        {
            if (TwinMainMenu.Instance != null && TwinMainMenu.Instance.IsPaused) return;
            EnsureStyles();
            float w = 920f;
            float rowH = 52f;
            float panelH = panelOpen ? Mathf.Min(1100f, Screen.height - 32f) : 64f;
            float x = Screen.width - w - 16f;
            float y = 16f;

            GUI.Box(new Rect(x, y, w, panelH), "");
            GUI.Label(new Rect(x + 16f, y + 10f, w - 90f, 48f), "Liberty 100 — DR Twin Sim", _titleStyle);
            if (GUI.Button(new Rect(x + w - 56f, y + 12f, 44f, 44f), panelOpen ? "–" : "+", _buttonStyle))
                panelOpen = !panelOpen;
            if (!panelOpen) return;

            float row = y + 72f;
            float labelW = 280f;
            float sliderX = x + labelW + 8f;
            float sliderW = w - labelW - 40f;

            GUI.Label(new Rect(x + 20f, row, labelW, rowH), $"OAT °C  {oatC:0.0}", _labelStyle);
            oatC = GUI.HorizontalSlider(new Rect(sliderX, row + 18f, sliderW, 24f), oatC, 10f, 42f);
            row += rowH;

            GUI.Label(new Rect(x + 20f, row, labelW, rowH), $"RH %  {rhPct:0.0}", _labelStyle);
            rhPct = GUI.HorizontalSlider(new Rect(sliderX, row + 18f, sliderW, 24f), rhPct, 20f, 95f);
            row += rowH;

            GUI.Label(new Rect(x + 20f, row, labelW, rowH), $"Hour ending  {hourEnding}", _labelStyle);
            hourEnding = Mathf.RoundToInt(GUI.HorizontalSlider(new Rect(sliderX, row + 18f, sliderW, 24f), hourEnding, 1, 24));
            row += rowH;

            GUI.Label(new Rect(x + 20f, row, labelW, rowH), $"Precool °F  {precoolF:0.0}", _labelStyle);
            precoolF = GUI.HorizontalSlider(new Rect(sliderX, row + 18f, sliderW, 24f), precoolF, 0f, 6f);
            row += rowH;

            GUI.Label(new Rect(x + 20f, row, labelW, rowH), $"Relax clg °F  {relaxClgF:0.0}", _labelStyle);
            relaxClgF = GUI.HorizontalSlider(new Rect(sliderX, row + 18f, sliderW, 24f), relaxClgF, 0f, 10f);
            row += rowH;

            GUI.Label(new Rect(x + 20f, row, w - 40f, rowH), $"Strategy:  {Strategies[strategyIndex]}", _labelStyle);
            row += 44f;
            if (GUI.Button(new Rect(x + 20f, row, (w - 56f) * 0.5f, 56f), "◀  Prev strategy", _buttonStyle))
                strategyIndex = (strategyIndex + Strategies.Length - 1) % Strategies.Length;
            if (GUI.Button(new Rect(x + 36f + (w - 56f) * 0.5f, row, (w - 56f) * 0.5f, 56f), "Next strategy  ▶", _buttonStyle))
                strategyIndex = (strategyIndex + 1) % Strategies.Length;
            row += 68f;

            GUI.Label(new Rect(x + 20f, row, w - 40f, rowH),
                $"2-hr event plays in:  {PlaybackLabels[playbackDurationIndex]}", _labelStyle);
            row += 44f;
            float btnW = (w - 64f) / 3f;
            for (int i = 0; i < 3; i++)
            {
                GUI.enabled = !_eventRunning;
                if (GUI.Button(new Rect(x + 20f + i * (btnW + 10f), row, btnW, 52f), PlaybackLabels[i], _buttonStyle))
                    playbackDurationIndex = i;
                GUI.enabled = true;
            }
            row += 64f;

            GUI.enabled = !_busy && !_eventRunning;
            if (GUI.Button(new Rect(x + 20f, row, w - 40f, 60f),
                    "Predict once  +  refresh temps", _buttonStyle))
                StartCoroutine(RunPredictOnce());
            GUI.enabled = true;
            row += 72f;

            GUI.enabled = !_busy;
            if (!_eventRunning)
            {
                if (GUI.Button(new Rect(x + 20f, row, w - 40f, 64f),
                        $"Run DR Event ({PlaybackLabels[playbackDurationIndex]})", _buttonStyle))
                {
                    if (_eventCo != null) StopCoroutine(_eventCo);
                    _eventCo = StartCoroutine(RunDrEvent());
                }
            }
            else
            {
                if (GUI.Button(new Rect(x + 20f, row, w - 40f, 64f), "Stop DR Event", _buttonStyle))
                    StopDrEvent();
            }
            GUI.enabled = true;
            row += 76f;

            // Land / Recover watch mode
            var drone = FindAnyObjectByType<DroneController>();
            bool parked = drone != null && drone.IsWatchParked;
            string landLabel = parked ? "Recover Drone  (Space)" : "Land Drone  (Space)";
            if (GUI.Button(new Rect(x + 20f, row, w - 40f, 72f), landLabel, _buttonStyle))
            {
                if (drone != null) drone.ToggleWatchLand();
            }
            row += 80f;
            GUI.Label(new Rect(x + 20f, row, w - 40f, 36f),
                "Space — silly land / recover (freeze cam, watch plant)", _labelStyle);
            row += 44f;

            if (_eventRunning)
            {
                float pct = _simHourProgress / SimWindowHours;
                GUI.Label(new Rect(x + 20f, row, w - 40f, 36f),
                    $"Event progress: {_simHourProgress:0.00} / {SimWindowHours:0} h  ({pct * 100f:0}%)", _labelStyle);
                row += 40f;
            }

            GUI.Label(new Rect(x + 20f, row, w - 40f, 36f),
                float.IsNaN(_lastKw) ? "Predicted facility kW:  —" : $"Predicted facility kW:  {_lastKw:0.0}",
                _labelStyle);
            row += 40f;
            GUI.Label(new Rect(x + 20f, row, w - 40f, 100f),
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
