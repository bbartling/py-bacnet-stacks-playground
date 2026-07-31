using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Procedural 2D machine sounds: AHU fans, CHW pump, chiller, cooling tower.</summary>
    public class MachineAudioHub : MonoBehaviour
    {
        public static MachineAudioHub Instance { get; private set; }

        [Range(0f, 1f)] public float masterVolume = 0.35f;

        AudioSource _ahu;
        AudioSource _pump;
        AudioSource _chiller;
        AudioSource _tower;
        float _ahuLoad = 0.6f;
        float _plantRun = 1f;

        public static MachineAudioHub Ensure()
        {
            if (Instance != null) return Instance;
            var go = GameObject.Find("MachineAudioHub") ?? new GameObject("MachineAudioHub");
            var hub = go.GetComponent<MachineAudioHub>() ?? go.AddComponent<MachineAudioHub>();
            return hub;
        }

        void Awake()
        {
            Instance = this;
            _ahu = MakeSrc("AHU_Whoosh", MakeNoise(180f, 0.4f));
            _pump = MakeSrc("Pump_Rumble", MakeNoise(70f, 0.5f));
            _chiller = MakeSrc("Chiller_Hum", MakeNoise(55f, 0.55f));
            _tower = MakeSrc("Tower_Whoosh", MakeNoise(140f, 0.35f));
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        AudioSource MakeSrc(string name, AudioClip clip)
        {
            var child = new GameObject(name);
            child.transform.SetParent(transform, false);
            var src = child.AddComponent<AudioSource>();
            src.clip = clip;
            src.loop = true;
            src.playOnAwake = false;
            src.spatialBlend = 0f;
            src.volume = 0f;
            src.priority = 80;
            return src;
        }

        static AudioClip MakeNoise(float baseHz, float amp)
        {
            const int sampleRate = 44100;
            var data = new float[sampleRate];
            for (int i = 0; i < sampleRate; i++)
            {
                float t = i / (float)sampleRate;
                float s =
                    0.5f * Mathf.Sin(2f * Mathf.PI * baseHz * t) +
                    0.3f * Mathf.Sin(2f * Mathf.PI * baseHz * 2f * t) +
                    0.15f * Mathf.Sin(2f * Mathf.PI * baseHz * 0.5f * t);
                s += (Mathf.PerlinNoise(t * 30f, baseHz * 0.01f) - 0.5f) * 0.25f;
                data[i] = Mathf.Clamp(s * amp, -1f, 1f);
            }
            var clip = AudioClip.Create($"Mach_{baseHz}", sampleRate, 1, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }

        public void SetAhuLoad(float load) => _ahuLoad = Mathf.Clamp01(load);

        public void SetPlantRunning(float run, bool menuPaused)
        {
            _plantRun = Mathf.Clamp01(run);
            if (menuPaused)
            {
                PauseAll();
                return;
            }
            PlayVol(_ahu, masterVolume * 0.55f * (0.3f + _ahuLoad), 0.85f + _ahuLoad * 0.4f);
            PlayVol(_pump, masterVolume * 0.4f * _plantRun, 0.9f + _plantRun * 0.2f);
            PlayVol(_chiller, masterVolume * 0.5f * _plantRun, 0.85f + _plantRun * 0.25f);
            PlayVol(_tower, masterVolume * 0.45f * _plantRun, 0.9f + _plantRun * 0.3f);
        }

        void PlayVol(AudioSource src, float vol, float pitch)
        {
            if (src == null) return;
            if (vol < 0.02f)
            {
                if (src.isPlaying) src.Pause();
                return;
            }
            if (!src.isPlaying) src.Play();
            src.volume = vol;
            src.pitch = pitch;
        }

        void PauseAll()
        {
            if (_ahu != null && _ahu.isPlaying) _ahu.Pause();
            if (_pump != null && _pump.isPlaying) _pump.Pause();
            if (_chiller != null && _chiller.isPlaying) _chiller.Pause();
            if (_tower != null && _tower.isPlaying) _tower.Pause();
        }
    }
}
