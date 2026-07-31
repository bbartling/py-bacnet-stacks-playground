using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Professional full-overlay title / pause menu with drone control legend.</summary>
    public class TwinMainMenu : MonoBehaviour
    {
        public static TwinMainMenu Instance { get; private set; }

        public bool startPaused = true;
        public bool IsPaused { get; private set; } = true;

        GUIStyle _title;
        GUIStyle _subtitle;
        GUIStyle _body;
        GUIStyle _btn;
        GUIStyle _card;
        bool _styles;

        void Awake()
        {
            Instance = this;
            IsPaused = startPaused;
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
                {
                    var src = drone.GetComponent<AudioSource>();
                    if (src != null && !src.isPlaying) src.Play();
                }
                MachineAudioHub.Ensure();
            }
        }

        void EnsureStyles()
        {
            if (_styles) return;
            _title = new GUIStyle(GUI.skin.label)
            {
                fontSize = 56,
                fontStyle = FontStyle.Bold,
                alignment = TextAnchor.MiddleCenter,
                wordWrap = true,
                normal = { textColor = new Color(0.92f, 0.96f, 0.94f) }
            };
            _subtitle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 22,
                alignment = TextAnchor.MiddleCenter,
                wordWrap = true,
                normal = { textColor = new Color(0.65f, 0.78f, 0.75f) }
            };
            _body = new GUIStyle(GUI.skin.label)
            {
                fontSize = 24,
                alignment = TextAnchor.UpperLeft,
                normal = { textColor = new Color(0.82f, 0.88f, 0.86f) },
                wordWrap = true
            };
            _btn = new GUIStyle(GUI.skin.button)
            {
                fontSize = 28,
                fontStyle = FontStyle.Bold,
                fixedHeight = 68
            };
            _card = new GUIStyle(GUI.skin.box)
            {
                padding = new RectOffset(28, 28, 24, 24)
            };
            _styles = true;
        }

        void OnGUI()
        {
            if (!IsPaused) return;
            EnsureStyles();

            // Near-fullscreen dim
            GUI.color = new Color(0.04f, 0.07f, 0.09f, 0.82f);
            GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
            GUI.color = Color.white;

            float w = Mathf.Clamp(Screen.width * 0.55f, 720f, 920f);
            float h = Mathf.Clamp(Screen.height * 0.72f, 560f, 720f);
            float x = (Screen.width - w) * 0.5f;
            float y = (Screen.height - h) * 0.5f;

            GUI.Box(new Rect(x, y, w, h), "", _card);
            GUI.Label(new Rect(x + 24f, y + 28f, w - 48f, 72f), "Liberty Building 100 Digital Twin", _title);
            GUI.Label(new Rect(x + 40f, y + 100f, w - 80f, 40f),
                "Demand-management flythrough  ·  DEMO plant & sensors  ·  not live BAS", _subtitle);

            GUI.Label(new Rect(x + 56f, y + 160f, w - 112f, 320f),
                "FLIGHT CONTROLS\n\n" +
                "  W / ↑                 Forward\n" +
                "  S / ↓                 Back\n" +
                "  A / ←                 Strafe left\n" +
                "  D / →                 Strafe right\n" +
                "  E / PageUp            Climb\n" +
                "  Q / PageDown          Descend\n" +
                "  Shift                 Boost\n" +
                "  Mouse                 Look\n" +
                "  Esc                   Pause / menu\n\n" +
                "Bonk the building — scrape, bounce, keep flying.\n" +
                "Roof: cool-focused x-ray AHUs  ·  courtyard chiller + tower.",
                _body);

            if (GUI.Button(new Rect(x + 100f, y + h - 100f, w - 200f, 68f), "Start Flight", _btn))
                SetPaused(false);
        }
    }
}
