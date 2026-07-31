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
                fontSize = 48,
                fontStyle = FontStyle.Bold,
                alignment = TextAnchor.MiddleCenter,
                wordWrap = true,
                normal = { textColor = new Color(0.92f, 0.96f, 0.94f) }
            };
            _subtitle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 20,
                alignment = TextAnchor.MiddleCenter,
                wordWrap = true,
                normal = { textColor = new Color(0.65f, 0.78f, 0.75f) }
            };
            _body = new GUIStyle(GUI.skin.label)
            {
                fontSize = 22,
                alignment = TextAnchor.UpperLeft,
                normal = { textColor = new Color(0.82f, 0.88f, 0.86f) },
                wordWrap = true
            };
            _btn = new GUIStyle(GUI.skin.button)
            {
                fontSize = 28,
                fontStyle = FontStyle.Bold,
                fixedHeight = 64
            };
            _btnSm = new GUIStyle(GUI.skin.button)
            {
                fontSize = 18,
                fontStyle = FontStyle.Bold,
                fixedHeight = 40
            };
            _card = new GUIStyle(GUI.skin.box)
            {
                padding = new RectOffset(32, 32, 28, 28)
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

            float w = Mathf.Clamp(Screen.width * 0.72f, 900f, 1100f);
            float h = Mathf.Clamp(Screen.height * 0.85f, 720f, 900f);
            float x = (Screen.width - w) * 0.5f;
            float y = (Screen.height - h) * 0.5f;

            GUI.Box(new Rect(x, y, w, h), "", _card);
            GUI.Label(new Rect(x + 40f, y + 24f, w - 80f, 90f), "Liberty Building 100 Digital Twin", _title);
            GUI.Label(new Rect(x + 48f, y + 110f, w - 96f, 36f),
                "Demand-management flythrough  ·  DEMO plant & sensors  ·  not live BAS", _subtitle);

            // Units toggle
            float ux = x + 56f;
            float uy = y + 155f;
            GUI.Label(new Rect(ux, uy, 220f, 36f), "Temperature units:", _body);
            bool wantF = useFahrenheit;
            if (GUI.Toggle(new Rect(ux + 220f, uy, 120f, 36f), !wantF, "  °C Metric"))
                wantF = false;
            if (GUI.Toggle(new Rect(ux + 360f, uy, 160f, 36f), wantF, "  °F Imperial"))
                wantF = true;
            if (wantF != useFahrenheit)
            {
                useFahrenheit = wantF;
                TempUnits.UseFahrenheit = wantF;
                RefreshAllTempLabels();
            }

            GUI.Label(new Rect(x + 56f, y + 205f, w - 112f, 380f),
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

            if (GUI.Button(new Rect(x + 120f, y + h - 95f, w - 240f, 64f), "Start Flight", _btn))
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
