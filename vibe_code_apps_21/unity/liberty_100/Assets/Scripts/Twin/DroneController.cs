using UnityEngine;
using UnityEngine.InputSystem;

namespace Vibe21.Twin
{
    /// <summary>
    /// Greyscale flyable drone. Space/L land, Space/R recover (watch mode). Climb = E/PageUp only.
    /// </summary>
    public class DroneController : MonoBehaviour
    {
        public float moveSpeed = 28f;
        public float verticalSpeed = 22f;
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
        public float collideRadius = 0.55f;
        public float bonkCooldown = 0.18f;
        public LayerMask collideMask = ~0;
        public float landDropSpeed = 18f;
        public float sillyLandDropSpeed = 38f;
        public float recoverZipSpeed = 42f;

        public bool IsWatchParked => _mode == FlightMode.Landed || _mode == FlightMode.Landing;

        float _yaw;
        float _pitch;
        AudioSource _motor;
        AudioSource _bonk;
        AudioSource _crash;
        AudioSource _scrape;
        float _load;
        bool _audioReady;
        float _bonkTimer;
        Vector3 _velocity;
        bool _scraping;

        enum FlightMode { Flying, Landing, Landed, Recovering }
        FlightMode _mode = FlightMode.Flying;
        Vector3 _preLandPos;
        Quaternion _preLandRot;
        Vector3 _frozenCamPos;
        Quaternion _frozenCamRot;
        bool _cameraFrozen;
        bool _flightAudioStarted;
        float _idlePropRpm = 120f;
        bool _sillyLand;
        float _tumbleSpin;

        void Awake()
        {
            if (enableMotorSound) EnsureMotorSound();
            EnsureCollisionAudio();
            EnsureBodyCollider();
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
            EnsureCollisionAudio();
        }

        public void NotifyFlightStarted()
        {
            _flightAudioStarted = true;
            EnsureMotorSound();
            if (_motor == null) return;
            _motor.Stop();
            _motor.time = 0f;
            _motor.loop = true;
            if (!IsMenuPaused())
                _motor.Play();
        }

        public void ToggleWatchLand()
        {
            if (_mode == FlightMode.Flying)
                BeginLand(silly: true);
            else if (_mode == FlightMode.Landed || _mode == FlightMode.Landing)
                BeginRecover();
        }

        void EnsureBodyCollider()
        {
            var col = GetComponent<SphereCollider>();
            if (col == null) col = gameObject.AddComponent<SphereCollider>();
            col.radius = collideRadius;
            col.isTrigger = false;
            var rb = GetComponent<Rigidbody>();
            if (rb == null) rb = gameObject.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
        }

        void EnsureMotorSound()
        {
            if (_audioReady && _motor != null && _motor.clip != null) return;
            _motor = gameObject.GetComponent<AudioSource>();
            if (_motor == null) _motor = gameObject.AddComponent<AudioSource>();
            if (_motor.clip == null)
                _motor.clip = MakeHumClip();
            _motor.loop = true;
            _motor.playOnAwake = false;
            _motor.spatialBlend = 0f;
            _motor.volume = motorVolume;
            _motor.bypassListenerEffects = true;
            _motor.ignoreListenerPause = true;
            _motor.priority = 64;
            _audioReady = true;
        }

        void EnsureCollisionAudio()
        {
            if (_bonk == null)
            {
                var go = new GameObject("BonkAudio");
                go.transform.SetParent(transform, false);
                _bonk = go.AddComponent<AudioSource>();
                _bonk.clip = MakeBonkClip();
                _bonk.loop = false;
                _bonk.playOnAwake = false;
                _bonk.spatialBlend = 0f;
                _bonk.volume = 0.7f;
            }
            if (_crash == null)
            {
                var go = new GameObject("CrashAudio");
                go.transform.SetParent(transform, false);
                _crash = go.AddComponent<AudioSource>();
                _crash.clip = MakeCrashClip();
                _crash.loop = false;
                _crash.playOnAwake = false;
                _crash.spatialBlend = 0f;
                _crash.volume = 0.95f;
            }
            if (_scrape == null)
            {
                var go = new GameObject("ScrapeAudio");
                go.transform.SetParent(transform, false);
                _scrape = go.AddComponent<AudioSource>();
                _scrape.clip = MakeScrapeClip();
                _scrape.loop = true;
                _scrape.playOnAwake = false;
                _scrape.spatialBlend = 0f;
                _scrape.volume = 0f;
            }
        }

        static AudioClip MakeHumClip()
        {
            const int sampleRate = 44100;
            var data = new float[sampleRate];
            for (int i = 0; i < sampleRate; i++)
            {
                float t = i / (float)sampleRate;
                float s =
                    0.55f * Mathf.Sin(2f * Mathf.PI * 110f * t) +
                    0.35f * Mathf.Sin(2f * Mathf.PI * 220f * t) +
                    0.20f * Mathf.Sin(2f * Mathf.PI * 330f * t) +
                    0.08f * Mathf.Sin(2f * Mathf.PI * 55f * t);
                s += (Mathf.PerlinNoise(t * 40f, 0.3f) - 0.5f) * 0.15f;
                data[i] = Mathf.Clamp(s * 0.55f, -1f, 1f);
            }
            var clip = AudioClip.Create("DroneHumLoud", sampleRate, 1, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }

        static AudioClip MakeBonkClip()
        {
            const int sampleRate = 44100;
            int n = sampleRate / 4;
            var data = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)sampleRate;
                float env = Mathf.Exp(-t * 18f);
                float s =
                    0.7f * Mathf.Sin(2f * Mathf.PI * 90f * t) * env +
                    0.5f * Mathf.Sin(2f * Mathf.PI * 180f * t) * env +
                    0.35f * Mathf.Sin(2f * Mathf.PI * 45f * t) * env +
                    (Random.value * 2f - 1f) * 0.25f * env;
                data[i] = Mathf.Clamp(s, -1f, 1f);
            }
            var clip = AudioClip.Create("DroneBonk", n, 1, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }

        static AudioClip MakeCrashClip()
        {
            const int sampleRate = 44100;
            int n = sampleRate;
            var data = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)sampleRate;
                float env = Mathf.Exp(-t * 4.5f);
                float s =
                    0.9f * Mathf.Sin(2f * Mathf.PI * 55f * t) * env +
                    0.7f * Mathf.Sin(2f * Mathf.PI * 90f * t) * env +
                    0.5f * Mathf.Sin(2f * Mathf.PI * 140f * t) * env +
                    (Random.value * 2f - 1f) * 0.55f * env +
                    0.35f * Mathf.Sin(2f * Mathf.PI * (30f + t * 80f) * t) * env;
                data[i] = Mathf.Clamp(s, -1f, 1f);
            }
            var clip = AudioClip.Create("DroneCrashSilly", n, 1, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }

        static AudioClip MakeScrapeClip()
        {
            const int sampleRate = 44100;
            var data = new float[sampleRate];
            for (int i = 0; i < sampleRate; i++)
            {
                float t = i / (float)sampleRate;
                float s = (Random.value * 2f - 1f) * 0.45f;
                s += 0.2f * Mathf.Sin(2f * Mathf.PI * 220f * t);
                s *= 0.55f + 0.45f * Mathf.PerlinNoise(t * 80f, 1.7f);
                data[i] = Mathf.Clamp(s, -1f, 1f);
            }
            var clip = AudioClip.Create("DroneScrape", sampleRate, 1, sampleRate, false);
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
                if (_scrape != null && _scrape.isPlaying) _scrape.Pause();
                return;
            }

            EnsureMotorSound();
            EnsureCollisionAudio();

            float dt = Time.unscaledDeltaTime;

            if (KeyDown(Key.Space)) ToggleWatchLand();
            if (KeyDown(Key.L)) BeginLand(silly: false);
            if (KeyDown(Key.R)) BeginRecover();

            switch (_mode)
            {
                case FlightMode.Landing:
                    TickLanding(dt);
                    return;
                case FlightMode.Landed:
                    TickLanded(dt);
                    return;
                case FlightMode.Recovering:
                    TickRecovering(dt);
                    return;
            }

            if (_flightAudioStarted && _motor != null && !_motor.isPlaying)
                _motor.Play();

            float mx = MouseDeltaX();
            float my = MouseDeltaY();
            _yaw += mx * lookSensitivity;
            _pitch -= my * lookSensitivity;
            _pitch = Mathf.Clamp(_pitch, minPitch, maxPitch);
            transform.rotation = Quaternion.Euler(0f, _yaw, 0f);

            float boost = (KeyHeld(Key.LeftShift) || KeyHeld(Key.RightShift)) ? boostMultiplier : 1f;

            Vector3 wish = Vector3.zero;
            if (KeyHeld(Key.W) || KeyHeld(Key.UpArrow)) wish += transform.forward;
            if (KeyHeld(Key.S) || KeyHeld(Key.DownArrow)) wish -= transform.forward;
            if (KeyHeld(Key.A) || KeyHeld(Key.LeftArrow)) wish -= transform.right;
            if (KeyHeld(Key.D) || KeyHeld(Key.RightArrow)) wish += transform.right;
            float vert = 0f;
            if (KeyHeld(Key.E) || KeyHeld(Key.PageUp)) vert += 1f;
            if (KeyHeld(Key.Q) || KeyHeld(Key.PageDown) || KeyHeld(Key.LeftCtrl)) vert -= 1f;
            if (wish.sqrMagnitude > 0f) wish = wish.normalized * (moveSpeed * boost);
            wish += Vector3.up * (vert * verticalSpeed * boost);

            _velocity = Vector3.Lerp(_velocity, wish, 1f - Mathf.Exp(-10f * dt));
            MoveWithCollision(_velocity * dt);

            _bonkTimer -= dt;
            _load = (wish.sqrMagnitude > 0.5f) ? 1.4f : 0.85f;
            SpinProps(_load, dt);
            if (_motor != null && _flightAudioStarted)
            {
                _motor.pitch = 0.9f + 0.45f * (_load - 0.85f);
                _motor.volume = motorVolume * (0.75f + 0.35f * (_load - 0.85f));
            }
            UpdateCamera();
        }

        void BeginLand(bool silly)
        {
            if (_mode != FlightMode.Flying) return;
            _sillyLand = silly;
            _tumbleSpin = silly ? Random.Range(220f, 420f) * (Random.value > 0.5f ? 1f : -1f) : 0f;
            _preLandPos = transform.position;
            _preLandRot = transform.rotation;
            if (cameraRig != null)
            {
                _frozenCamPos = cameraRig.position;
                _frozenCamRot = cameraRig.rotation;
            }
            _cameraFrozen = true;
            _velocity = Vector3.zero;
            _mode = FlightMode.Landing;
        }

        void BeginRecover()
        {
            if (_mode != FlightMode.Landed && _mode != FlightMode.Landing) return;
            _sillyLand = false;
            _mode = FlightMode.Recovering;
            _cameraFrozen = false;
            if (_motor != null && _flightAudioStarted)
            {
                _motor.volume = motorVolume;
                if (!_motor.isPlaying) _motor.Play();
            }
        }

        void TickLanding(float dt)
        {
            _bonkTimer -= dt;
            float dropSpd = _sillyLand ? sillyLandDropSpeed : landDropSpeed;
            MoveWithCollision(Vector3.down * (dropSpd * dt));

            if (_sillyLand)
            {
                _yaw += _tumbleSpin * dt;
                transform.rotation = Quaternion.Euler(Random.Range(-25f, 25f), _yaw, Random.Range(-35f, 35f));
            }

            bool onGround = false;
            if (Physics.SphereCast(transform.position + Vector3.up * 2f, collideRadius * 0.9f, Vector3.down, out var ground, 4f, collideMask, QueryTriggerInteraction.Ignore))
            {
                if (!ground.collider.transform.IsChildOf(transform))
                {
                    float minY = ground.point.y + collideRadius + 0.05f;
                    if (transform.position.y <= minY + 0.08f)
                        onGround = true;
                }
            }

            SpinProps(0.35f, dt);
            if (_motor != null)
            {
                _motor.pitch = Mathf.Lerp(_motor.pitch, 0.55f, 0.08f);
                _motor.volume = Mathf.Lerp(_motor.volume, motorVolume * 0.15f, 0.08f);
            }
            if (_cameraFrozen && cameraRig != null)
            {
                cameraRig.position = _frozenCamPos;
                cameraRig.rotation = _frozenCamRot;
            }

            if (onGround)
            {
                if (_bonkTimer <= 0f)
                {
                    if (_sillyLand) PlayCrash();
                    else PlayBonk(0.55f);
                    _bonkTimer = 0.8f;
                }
                _mode = FlightMode.Landed;
                _velocity = Vector3.zero;
                transform.rotation = Quaternion.Euler(12f, _yaw, Random.Range(-8f, 8f));
                if (_motor != null && _motor.isPlaying) _motor.Pause();
            }
        }

        void TickLanded(float dt)
        {
            SpinProps(_idlePropRpm / Mathf.Max(1f, propRpm), dt);
            if (_motor != null && _motor.isPlaying) _motor.Pause();
            if (_scrape != null && _scrape.isPlaying) _scrape.Pause();
            if (_cameraFrozen && cameraRig != null)
            {
                cameraRig.position = _frozenCamPos;
                cameraRig.rotation = _frozenCamRot;
            }
        }

        void TickRecovering(float dt)
        {
            Vector3 target = _preLandPos;
            Vector3 to = target - transform.position;
            float dist = to.magnitude;
            if (dist < 0.15f)
            {
                transform.position = target;
                transform.rotation = _preLandRot;
                _yaw = _preLandRot.eulerAngles.y;
                _velocity = Vector3.zero;
                _mode = FlightMode.Flying;
                if (_motor != null && _flightAudioStarted && !_motor.isPlaying)
                    _motor.Play();
                return;
            }

            transform.position += to.normalized * Mathf.Min(dist, recoverZipSpeed * dt);
            _load = 1.5f;
            SpinProps(_load, dt);
            if (_motor != null && _flightAudioStarted)
            {
                if (!_motor.isPlaying) _motor.Play();
                _motor.pitch = 1.2f;
                _motor.volume = motorVolume;
            }
            UpdateCamera();
        }

        void MoveWithCollision(Vector3 delta)
        {
            _scraping = false;
            if (delta.sqrMagnitude < 1e-8f) return;

            Vector3 pos = transform.position;
            float dist = delta.magnitude;
            Vector3 dir = delta / dist;
            var hits = Physics.SphereCastAll(pos, collideRadius * 0.95f, dir, dist + 0.05f, collideMask, QueryTriggerInteraction.Ignore);
            System.Array.Sort(hits, (a, b) => a.distance.CompareTo(b.distance));

            bool hitSomething = false;
            foreach (var hit in hits)
            {
                if (hit.collider == null) continue;
                if (hit.collider.transform.IsChildOf(transform) || hit.collider.transform == transform)
                    continue;
                hitSomething = true;
                pos = hit.point + hit.normal * (collideRadius + 0.05f);
                float into = Vector3.Dot(_velocity, -hit.normal);
                if (into > 0f)
                    _velocity += hit.normal * into * 1.35f;
                _velocity *= 0.55f;

                float impact = Mathf.Abs(into);
                if (impact > 2f && _bonkTimer <= 0f)
                {
                    PlayBonk(Mathf.Clamp01(impact / 30f));
                    _bonkTimer = bonkCooldown;
                }
                var horiz = _velocity; horiz.y = 0f;
                if (impact > 0.5f || Vector3.Dot(horiz, -hit.normal) > 0.1f)
                    _scraping = true;
                break;
            }

            if (!hitSomething)
                pos += delta;

            if (Physics.SphereCast(pos + Vector3.up * 2f, collideRadius * 0.9f, Vector3.down, out var ground, 4f, collideMask, QueryTriggerInteraction.Ignore))
            {
                if (!ground.collider.transform.IsChildOf(transform))
                {
                    float minY = ground.point.y + collideRadius + 0.05f;
                    if (pos.y < minY)
                    {
                        pos.y = minY;
                        if (_velocity.y < 0f)
                        {
                            if (_velocity.y < -3f && _bonkTimer <= 0f)
                            {
                                PlayBonk(Mathf.Clamp01(-_velocity.y / 25f));
                                _bonkTimer = bonkCooldown;
                            }
                            _velocity.y = Mathf.Abs(_velocity.y) * 0.35f;
                            _scraping = true;
                        }
                    }
                }
            }

            transform.position = pos;
            UpdateScrape();
        }

        void PlayBonk(float strength)
        {
            if (_bonk == null) return;
            _bonk.pitch = 0.75f + Random.Range(0f, 0.5f);
            _bonk.volume = 0.35f + 0.55f * strength;
            _bonk.Play();
        }

        void PlayCrash()
        {
            if (_crash == null) return;
            _crash.pitch = 0.85f + Random.Range(0f, 0.3f);
            _crash.volume = 0.9f;
            _crash.Play();
        }

        void UpdateScrape()
        {
            if (_scrape == null) return;
            if (_scraping)
            {
                if (!_scrape.isPlaying) _scrape.Play();
                _scrape.volume = Mathf.Lerp(_scrape.volume, 0.35f, 0.2f);
                _scrape.pitch = 0.9f + Random.Range(0f, 0.25f);
            }
            else
            {
                _scrape.volume = Mathf.Lerp(_scrape.volume, 0f, 0.25f);
                if (_scrape.volume < 0.02f && _scrape.isPlaying) _scrape.Pause();
            }
        }

        void SpinProps(float load, float dt)
        {
            if (rotors == null) return;
            float deg = propRpm * load * 6f * dt;
            foreach (var r in rotors)
            {
                if (r == null) continue;
                r.Rotate(0f, deg, 0f, Space.Self);
            }
        }

        void UpdateCamera()
        {
            if (cameraRig == null || _cameraFrozen) return;
            var targetPos = transform.TransformPoint(cameraOffset);
            cameraRig.position = Vector3.Lerp(cameraRig.position, targetPos, 14f * Time.unscaledDeltaTime);
            cameraRig.rotation = Quaternion.Euler(_pitch, _yaw, 0f);
        }

        static bool KeyDown(Key key)
        {
            if (Keyboard.current != null && Keyboard.current[key].wasPressedThisFrame)
                return true;
            try
            {
                switch (key)
                {
                    case Key.L: return Input.GetKeyDown(KeyCode.L);
                    case Key.R: return Input.GetKeyDown(KeyCode.R);
                    case Key.Space: return Input.GetKeyDown(KeyCode.Space);
                }
            }
            catch { }
            return false;
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
                    case Key.LeftCtrl: return Input.GetKey(KeyCode.LeftControl);
                    case Key.LeftShift: return Input.GetKey(KeyCode.LeftShift);
                    case Key.RightShift: return Input.GetKey(KeyCode.RightShift);
                    case Key.UpArrow: return Input.GetKey(KeyCode.UpArrow);
                    case Key.DownArrow: return Input.GetKey(KeyCode.DownArrow);
                    case Key.LeftArrow: return Input.GetKey(KeyCode.LeftArrow);
                    case Key.RightArrow: return Input.GetKey(KeyCode.RightArrow);
                    case Key.PageUp: return Input.GetKey(KeyCode.PageUp);
                    case Key.PageDown: return Input.GetKey(KeyCode.PageDown);
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
