using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Game-style title / pause menu with drone control legend.</summary>
    public class TwinMainMenu : MonoBehaviour
    {
        public static TwinMainMenu Instance { get; private set; }

        public bool startPaused = true;
        public bool IsPaused { get; private set; } = true;

        GUIStyle _title;
        GUIStyle _body;
        GUIStyle _btn;
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
            // Don't freeze AudioListener / whole engine — only gate gameplay via IsPaused
            Time.timeScale = 1f;
            if (!paused)
            {
                var drone = FindAnyObjectByType<DroneController>();
                if (drone != null)
                {
                    var src = drone.GetComponent<AudioSource>();
                    if (src != null && !src.isPlaying) src.Play();
                }
            }
        }

        void EnsureStyles()
        {
            if (_styles) return;
            _title = new GUIStyle(GUI.skin.label)
            {
                fontSize = 42,
                fontStyle = FontStyle.Bold,
                alignment = TextAnchor.MiddleCenter,
                normal = { textColor = new Color(0.85f, 0.95f, 0.9f) }
            };
            _body = new GUIStyle(GUI.skin.label)
            {
                fontSize = 18,
                alignment = TextAnchor.UpperLeft,
                normal = { textColor = new Color(0.75f, 0.85f, 0.82f) },
                wordWrap = true
            };
            _btn = new GUIStyle(GUI.skin.button)
            {
                fontSize = 22,
                fontStyle = FontStyle.Bold,
                fixedHeight = 52
            };
            _styles = true;
        }

        void OnGUI()
        {
            if (!IsPaused) return;
            EnsureStyles();
            float w = Mathf.Min(640f, Screen.width - 40f);
            float h = 420f;
            float x = (Screen.width - w) * 0.5f;
            float y = (Screen.height - h) * 0.5f;

            // Dim backdrop
            GUI.color = new Color(0.05f, 0.1f, 0.1f, 0.72f);
            GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
            GUI.color = Color.white;

            GUI.Box(new Rect(x, y, w, h), "");
            GUI.Label(new Rect(x + 16f, y + 24f, w - 32f, 56f), "Liberty Building 100 Digital Twin!", _title);
            GUI.Label(new Rect(x + 40f, y + 100f, w - 80f, 200f),
                "DRONE CONTROLS\n\n" +
                "  W / ↑          Forward\n" +
                "  S / ↓          Back\n" +
                "  A / ←          Strafe left\n" +
                "  D / →          Strafe right\n" +
                "  E / PageUp     Climb\n" +
                "  Q / PageDown   Descend\n" +
                "  Shift          Boost\n" +
                "  Mouse          Look\n" +
                "  Esc            Pause / menu\n\n" +
                "Roof AHUs: DEMO leave / mix / return °C (x-ray cutaway).\n" +
                "Ducts + sensors are illustrative — not live BAS.",
                _body);

            if (GUI.Button(new Rect(x + 80f, y + h - 72f, w - 160f, 52f), "Start Flight", _btn))
                SetPaused(false);
        }
    }
}
