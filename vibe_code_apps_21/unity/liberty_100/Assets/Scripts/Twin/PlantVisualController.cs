using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Drives chiller/tower spin + machine audio from DR strategy.
    /// chiller_off / hvac_off → plant stops visually and audibly.
    /// </summary>
    public class PlantVisualController : MonoBehaviour
    {
        public Transform chillerRoot;
        public Transform towerRoot;
        public Transform chillerSpin;
        public Transform towerSpin;
        public float chillerRpm = 120f;
        public float towerRpm = 80f;
        [Range(0f, 1.5f)] public float plantLoad = 1f;
        public bool plantRunning = true;

        MachineAudioHub _audio;
        TextMesh _chillerLabel;
        TextMesh _towerLabel;

        void Start()
        {
            _audio = MachineAudioHub.Ensure();
            if (chillerRoot != null)
                _chillerLabel = chillerRoot.GetComponentInChildren<TextMesh>();
            if (towerRoot != null)
                _towerLabel = towerRoot.GetComponentInChildren<TextMesh>();
        }

        void Update()
        {
            bool paused = TwinMainMenu.Instance != null && TwinMainMenu.Instance.IsPaused;
            float run = (!paused && plantRunning) ? plantLoad : 0f;
            float dt = Time.deltaTime;
            if (chillerSpin != null && run > 0.02f)
                chillerSpin.Rotate(0f, chillerRpm * run * 6f * dt, 0f, Space.Self);
            if (towerSpin != null && run > 0.02f)
                towerSpin.Rotate(0f, towerRpm * run * 6f * dt, 0f, Space.Self);

            if (_audio != null)
                _audio.SetPlantRunning(run, paused);
        }

        public void ApplyStrategy(string strategyId, float facilityKw)
        {
            bool off = !string.IsNullOrEmpty(strategyId) &&
                       (strategyId.Contains("chiller_off") || strategyId == "hvac_off" ||
                        strategyId.Contains("precool_chiller_off"));
            plantRunning = !off;
            if (off)
                plantLoad = 0f;
            else
            {
                float t = Mathf.InverseLerp(120f, 320f, facilityKw);
                plantLoad = Mathf.Clamp(0.4f + t * 0.8f, 0.25f, 1.3f);
                if (!string.IsNullOrEmpty(strategyId) && strategyId.Contains("precool") && !strategyId.Contains("chiller"))
                    plantLoad = Mathf.Min(1.4f, plantLoad * 1.15f);
            }

            if (_chillerLabel != null)
                _chillerLabel.text = plantRunning
                    ? $"Main Chiller\nON  load {plantLoad:0.00}"
                    : "Main Chiller\nOFF — DR shed";
            if (_towerLabel != null)
                _towerLabel.text = plantRunning
                    ? "Cooling Tower\nON DEMO"
                    : "Cooling Tower\nOFF";

            foreach (var spin in FindObjectsByType<AhuFanSpin>())
                spin.SetLoadFromStrategy(strategyId, facilityKw);

            if (_audio != null)
                _audio.SetAhuLoad(plantRunning ? plantLoad : 0.05f);
        }

        void LateUpdate()
        {
            Face(_chillerLabel);
            Face(_towerLabel);
        }

        static void Face(TextMesh tm)
        {
            if (tm == null) return;
            var cam = Camera.main;
            if (cam == null) return;
            tm.transform.rotation = Quaternion.LookRotation(tm.transform.position - cam.transform.position);
        }
    }
}
