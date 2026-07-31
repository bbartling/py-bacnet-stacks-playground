using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Full-overlay title / pause menu with °F/°C toggle and flight legend.</summary>
    public class TwinMainMenu : MonoBehaviour
    {
        public static TwinMainMenu Instance { get; private set; }

        public bool startPaused = true;
        public bool IsPaused { get; private set; } = true;
        public bool useFahrenheit;

        GUIStyle _title;
        GUIStyle _subtitle;
        GUIStyle _body;
        GUIStyle _btn;
        GUIStyle _btnSm;
        GUIStyle _card;
        bool _styles;

        void Awake()
        {
            Instance = this;
            IsPaused = startPaused;
            TempUnits.UseFahrenheit = useFahrenheit;
            Time.timeScale = 1f;
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            Time.timeScale = 1f;
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.Escape))
                SetPaused(!IsPaused);
        }

        public void SetPaused(bool paused)
        {
            IsPaused = paused;
            Time.timeScale = 1f;
            if (!paused)
            {
                var drone = FindAnyObjectByType<DroneController>();
                if (drone != null)
                    drone.NotifyFlightStarted();
                MachineAudioHub.Ensure();
            }
        }

        void EnsureStyles()
        {
            if (_styles) return;
            _title = new GUIStyle(GUI.skin.label)
            {
                fontSize = 96,
                fontStyle = FontStyle.Bold,
                alignment = TextAnchor.MiddleCenter,
                wordWrap = true,
                normal = { textColor = new Color(0.92f, 0.96f, 0.94f) }
            };
            _subtitle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 40,
                alignment = TextAnchor.MiddleCenter,
                wordWrap = true,
                normal = { textColor = new Color(0.65f, 0.78f, 0.75f) }
            };
            _body = new GUIStyle(GUI.skin.label)
            {
                fontSize = 44,
                alignment = TextAnchor.UpperLeft,
                normal = { textColor = new Color(0.82f, 0.88f, 0.86f) },
                wordWrap = true
            };
            _btn = new GUIStyle(GUI.skin.button)
            {
                fontSize = 56,
                fontStyle = FontStyle.Bold,
                fixedHeight = 128
            };
            _btnSm = new GUIStyle(GUI.skin.button)
            {
                fontSize = 36,
                fontStyle = FontStyle.Bold,
                fixedHeight = 80
            };
            _card = new GUIStyle(GUI.skin.box)
            {
                padding = new RectOffset(64, 64, 56, 56)
            };
            _styles = true;
        }

        void OnGUI()
        {
            if (!IsPaused) return;
            EnsureStyles();

            GUI.color = new Color(0.04f, 0.07f, 0.09f, 0.85f);
            GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
            GUI.color = Color.white;

            float w = Mathf.Min(Screen.width * 0.92f, Mathf.Max(Screen.width * 0.72f, 1800f));
            float h = Mathf.Min(Screen.height * 0.92f, Mathf.Max(Screen.height * 0.85f, 1440f));
            w = Mathf.Min(w, Screen.width * 0.92f);
            h = Mathf.Min(h, Screen.height * 0.92f);
            float x = (Screen.width - w) * 0.5f;
            float y = (Screen.height - h) * 0.5f;

            GUI.Box(new Rect(x, y, w, h), "", _card);
            GUI.Label(new Rect(x + 80f, y + 48f, w - 160f, 180f), "Liberty Building 100 Digital Twin", _title);
            GUI.Label(new Rect(x + 96f, y + 220f, w - 192f, 72f),
                "Demand-management flythrough  ·  DEMO plant & sensors  ·  not live BAS", _subtitle);

            float ux = x + 112f;
            float uy = y + 310f;
            GUI.Label(new Rect(ux, uy, 440f, 72f), "Temperature units:", _body);
            bool wantF = useFahrenheit;
            if (GUI.Toggle(new Rect(ux + 440f, uy, 240f, 72f), !wantF, "  °C Metric"))
                wantF = false;
            if (GUI.Toggle(new Rect(ux + 720f, uy, 320f, 72f), wantF, "  °F Imperial"))
                wantF = true;
            if (wantF != useFahrenheit)
            {
                useFahrenheit = wantF;
                TempUnits.UseFahrenheit = wantF;
                RefreshAllTempLabels();
            }

            GUI.Label(new Rect(x + 112f, y + 410f, w - 224f, 760f),
                "FLIGHT CONTROLS\n\n" +
                "  W / ↑                 Forward\n" +
                "  S / ↓                 Back\n" +
                "  A / ←                 Strafe left\n" +
                "  D / →                 Strafe right\n" +
                "  E / PageUp            Climb\n" +
                "  Q / PageDown          Descend\n" +
                "  Shift                 Boost\n" +
                "  Mouse                 Look\n" +
                "  L                     Land (drop + freeze camera)\n" +
                "  R                     Recover (zip back up)\n" +
                "  Esc                   Pause / menu\n\n" +
                "Peer through glass for floor zone temps. Roof: x-ray AHUs + chiller + tower.",
                _body);

            if (GUI.Button(new Rect(x + 240f, y + h - 190f, w - 480f, 128f), "Start Flight", _btn))
                SetPaused(false);
        }

        public static void RefreshAllTempLabels()
        {
            foreach (var s in Object.FindObjectsByType<ZoneTempSensor>(FindObjectsSortMode.None))
                s.ApplyVisual();
            foreach (var a in Object.FindObjectsByType<AhuAirTempDisplay>(FindObjectsSortMode.None))
                a.RefreshLabel();
        }
    }
}
