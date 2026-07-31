using UnityEngine;
using UnityEngine.InputSystem;

namespace Vibe21.Twin
{
    /// <summary>
    /// Flyable drone — WASD / arrows. Props spin on SpinPivot local Y.
    /// Loud 2D motor hum (audible over scene).
    /// </summary>
    public class DroneController : MonoBehaviour
    {
        public float moveSpeed = 28f;
        public float boostMultiplier = 2.5f;
        public float lookSensitivity = 2.0f;
        public float minPitch = -80f;
        public float maxPitch = 80f;
        public Transform cameraRig;
        public Vector3 cameraOffset = new Vector3(0f, 1.4f, -3.8f);
        public Transform[] rotors;
        public float propRpm = 1800f;
        public bool lockCursorOnPlay = false;
        public bool enableMotorSound = true;
        [Range(0f, 1f)] public float motorVolume = 0.45f;

        float _yaw;
        float _pitch;
        AudioSource _motor;
        float _load;
        bool _audioReady;

        void Awake()
        {
            // Build audio early so Play Mode always has a source
            if (enableMotorSound)
                EnsureMotorSound();
        }

        void Start()
        {
            var e = transform.eulerAngles;
            _yaw = e.y;
            _pitch = 12f;
            if (cameraRig == null && Camera.main != null)
                cameraRig = Camera.main.transform;
            if (cameraRig != null)
            {
                var freefly = cameraRig.GetComponent<DroneFlyCamera>();
                if (freefly != null) freefly.enabled = false;
            }
            if (lockCursorOnPlay)
            {
                Cursor.lockState = CursorLockMode.Locked;
                Cursor.visible = false;
            }
            EnsureMotorSound();
            if (_motor != null && !IsMenuPaused())
                _motor.Play();
        }

        void EnsureMotorSound()
        {
            if (_audioReady && _motor != null) return;
            _motor = gameObject.GetComponent<AudioSource>();
            if (_motor == null) _motor = gameObject.AddComponent<AudioSource>();
            if (_motor.clip == null)
                _motor.clip = MakeHumClip();
            _motor.loop = true;
            _motor.playOnAwake = false;
            _motor.spatialBlend = 0f; // 2D — always hear it
            _motor.volume = motorVolume;
            _motor.pitch = 1f;
            _motor.bypassListenerEffects = true;
            _motor.ignoreListenerPause = true;
            _motor.priority = 64;
            _audioReady = true;
        }

        static AudioClip MakeHumClip()
        {
            const int sampleRate = 44100;
            const float secs = 1.0f;
            int n = sampleRate;
            var data = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)sampleRate;
                // Stronger buzzing motor — audible on laptop speakers
                float s =
                    0.55f * Mathf.Sin(2f * Mathf.PI * 110f * t) +
                    0.35f * Mathf.Sin(2f * Mathf.PI * 220f * t) +
                    0.20f * Mathf.Sin(2f * Mathf.PI * 330f * t) +
                    0.08f * Mathf.Sin(2f * Mathf.PI * 55f * t);
                // Light noise for "prop wash"
                s += (Mathf.PerlinNoise(t * 40f, 0.3f) - 0.5f) * 0.15f;
                data[i] = Mathf.Clamp(s * 0.55f, -1f, 1f);
            }
            var clip = AudioClip.Create("DroneHumLoud", n, 1, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }

        static bool IsMenuPaused()
        {
            var menu = TwinMainMenu.Instance;
            return menu != null && menu.IsPaused;
        }

        void Update()
        {
            if (IsMenuPaused())
            {
                if (_motor != null && _motor.isPlaying) _motor.Pause();
                return;
            }

            EnsureMotorSound();
            if (_motor != null)
            {
                if (!_motor.isPlaying) _motor.Play();
                // UnPause if previously paused
                if (_motor.isPlaying == false) _motor.UnPause();
            }

            float mx = MouseDeltaX();
            float my = MouseDeltaY();
            _yaw += mx * lookSensitivity;
            _pitch -= my * lookSensitivity;
            _pitch = Mathf.Clamp(_pitch, minPitch, maxPitch);
            transform.rotation = Quaternion.Euler(0f, _yaw, 0f);

            Vector3 wish = Vector3.zero;
            if (KeyHeld(Key.W) || KeyHeld(Key.UpArrow)) wish += transform.forward;
            if (KeyHeld(Key.S) || KeyHeld(Key.DownArrow)) wish -= transform.forward;
            if (KeyHeld(Key.A) || KeyHeld(Key.LeftArrow)) wish -= transform.right;
            if (KeyHeld(Key.D) || KeyHeld(Key.RightArrow)) wish += transform.right;
            if (KeyHeld(Key.E) || KeyHeld(Key.Space)) wish += Vector3.up;
            if (KeyHeld(Key.Q) || KeyHeld(Key.LeftCtrl)) wish -= Vector3.up;

            float boost = (KeyHeld(Key.LeftShift) || KeyHeld(Key.RightShift)) ? boostMultiplier : 1f;
            if (wish.sqrMagnitude > 0f)
                transform.position += wish.normalized * (moveSpeed * boost * Time.unscaledDeltaTime);

            // Use unscaledDeltaTime so props still spin if timescale glitches
            float dt = Time.unscaledDeltaTime;
            _load = wish.sqrMagnitude > 0.01f ? 1.4f : 0.85f;
            SpinProps(_load, dt);
            if (_motor != null)
            {
                _motor.pitch = 0.9f + 0.45f * (_load - 0.85f);
                _motor.volume = motorVolume * (0.75f + 0.35f * (_load - 0.85f));
            }
            UpdateCamera();
        }

        void SpinProps(float load, float dt)
        {
            if (rotors == null) return;
            float deg = propRpm * load * 6f * dt;
            foreach (var r in rotors)
            {
                if (r == null) continue;
                // Local Y = up for SpinPivot (procedural drone). Guaranteed correct.
                r.Rotate(0f, deg, 0f, Space.Self);
            }
        }

        void UpdateCamera()
        {
            if (cameraRig == null) return;
            var targetPos = transform.TransformPoint(cameraOffset);
            cameraRig.position = Vector3.Lerp(cameraRig.position, targetPos, 14f * Time.unscaledDeltaTime);
            cameraRig.rotation = Quaternion.Euler(_pitch, _yaw, 0f);
        }

        static bool KeyHeld(Key key)
        {
            if (Keyboard.current != null && Keyboard.current[key].isPressed)
                return true;
            try
            {
                switch (key)
                {
                    case Key.W: return Input.GetKey(KeyCode.W);
                    case Key.A: return Input.GetKey(KeyCode.A);
                    case Key.S: return Input.GetKey(KeyCode.S);
                    case Key.D: return Input.GetKey(KeyCode.D);
                    case Key.E: return Input.GetKey(KeyCode.E);
                    case Key.Q: return Input.GetKey(KeyCode.Q);
                    case Key.Space: return Input.GetKey(KeyCode.Space);
                    case Key.LeftCtrl: return Input.GetKey(KeyCode.LeftControl);
                    case Key.LeftShift: return Input.GetKey(KeyCode.LeftShift);
                    case Key.RightShift: return Input.GetKey(KeyCode.RightShift);
                    case Key.UpArrow: return Input.GetKey(KeyCode.UpArrow);
                    case Key.DownArrow: return Input.GetKey(KeyCode.DownArrow);
                    case Key.LeftArrow: return Input.GetKey(KeyCode.LeftArrow);
                    case Key.RightArrow: return Input.GetKey(KeyCode.RightArrow);
                }
            }
            catch { }
            return false;
        }

        static float MouseDeltaX()
        {
            if (Mouse.current != null) return Mouse.current.delta.x.ReadValue() * 0.05f;
            try { return Input.GetAxis("Mouse X"); } catch { return 0f; }
        }

        static float MouseDeltaY()
        {
            if (Mouse.current != null) return Mouse.current.delta.y.ReadValue() * 0.05f;
            try { return Input.GetAxis("Mouse Y"); } catch { return 0f; }
        }
    }
}
