using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Vibe21.Twin
{
    /// <summary>
    /// Flyable drone — WASD / arrows + motor hum. Props spin around world-up.
    /// </summary>
    public class DroneController : MonoBehaviour
    {
        public float moveSpeed = 28f;
        public float boostMultiplier = 2.5f;
        public float lookSensitivity = 2.0f;
        public float minPitch = -80f;
        public float maxPitch = 80f;
        public Transform cameraRig;
        public Vector3 cameraOffset = new Vector3(0f, 1.2f, -3.5f);
        public Transform[] rotors;
        public float propRpm = 1400f;
        public bool lockCursorOnPlay = false;
        public bool enableMotorSound = true;
        [Range(0f, 0.4f)] public float motorVolume = 0.12f;

        float _yaw;
        float _pitch;
        AudioSource _motor;
        float _load;

        void Start()
        {
            var e = transform.eulerAngles;
            _yaw = e.y;
            _pitch = 15f;
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
            if (enableMotorSound)
                SetupMotorSound();
        }

        void SetupMotorSound()
        {
            _motor = gameObject.GetComponent<AudioSource>();
            if (_motor == null) _motor = gameObject.AddComponent<AudioSource>();
            _motor.clip = MakeHumClip();
            _motor.loop = true;
            _motor.spatialBlend = 0.65f;
            _motor.volume = motorVolume;
            _motor.playOnAwake = false;
            _motor.Play();
        }

        static AudioClip MakeHumClip()
        {
            const int sampleRate = 22050;
            const float secs = 0.4f;
            int n = Mathf.RoundToInt(sampleRate * secs);
            var data = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)sampleRate;
                // Soft multi-harmonic buzz (not a siren)
                float s =
                    0.45f * Mathf.Sin(2f * Mathf.PI * 85f * t) +
                    0.25f * Mathf.Sin(2f * Mathf.PI * 170f * t) +
                    0.12f * Mathf.Sin(2f * Mathf.PI * 255f * t);
                data[i] = s * 0.35f;
            }
            var clip = AudioClip.Create("DroneHum", n, 1, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }

        void Update()
        {
            // Menu may freeze us
            var menu = TwinMainMenu.Instance;
            if (menu != null && menu.IsPaused)
            {
                if (_motor != null && _motor.isPlaying) _motor.Pause();
                return;
            }
            if (_motor != null && !_motor.isPlaying && enableMotorSound) _motor.UnPause();

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
                transform.position += wish.normalized * (moveSpeed * boost * Time.deltaTime);

            _load = wish.sqrMagnitude > 0.01f ? 1.35f : 0.75f;
            SpinProps(_load);
            if (_motor != null)
            {
                _motor.pitch = 0.85f + 0.35f * (_load - 0.75f);
                _motor.volume = motorVolume * (0.7f + 0.3f * _load);
            }
            UpdateCamera();
        }

        void SpinProps(float load)
        {
            if (rotors == null) return;
            float deg = propRpm * load * 6f * Time.deltaTime;
            foreach (var r in rotors)
                SpinUtil.SpinWorldUp(r, deg);
        }

        void UpdateCamera()
        {
            if (cameraRig == null) return;
            var targetPos = transform.TransformPoint(cameraOffset);
            cameraRig.position = Vector3.Lerp(cameraRig.position, targetPos, 12f * Time.deltaTime);
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
