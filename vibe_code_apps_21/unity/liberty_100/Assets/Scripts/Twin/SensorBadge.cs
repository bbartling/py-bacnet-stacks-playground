using UnityEngine;

namespace Vibe21.Twin
{
    public enum SensorBadgeKind
    {
        ZoneTemp,
        AhuLeave,
        AhuMix,
        AhuReturn,
        AhuOa,
        ChillerStatus,
        TowerStatus
    }

    /// <summary>
    /// Manually placeable sensor icon + live reading (no LOS occlusion).
    /// </summary>
    public class SensorBadge : MonoBehaviour
    {
        public SensorBadgeKind kind = SensorBadgeKind.ZoneTemp;
        public string zoneEntityId;
        public string airLoopName = "VAV Sys 1";
        public bool isAhu2;
        public TextMesh label;
        public Renderer icon;

        ZoneTempController _temps;
        AhuAirTempDisplay _ahu;
        PlantVisualController _plant;

        void Start()
        {
            _temps = FindAnyObjectByType<ZoneTempController>();
            RefreshBindings();
        }

        public void RefreshBindings()
        {
            _ahu = null;
            foreach (var a in FindObjectsByType<AhuAirTempDisplay>())
            {
                bool match = isAhu2 ? a.isAhu2 : !a.isAhu2;
                if (!string.IsNullOrEmpty(airLoopName) && a.airLoopName == airLoopName)
                {
                    _ahu = a;
                    break;
                }
                if (_ahu == null && match) _ahu = a;
            }
            _plant = FindAnyObjectByType<PlantVisualController>();
            if (_temps == null)
                _temps = FindAnyObjectByType<ZoneTempController>();
        }

        void LateUpdate()
        {
            if (label == null) return;
            var cam = Camera.main;
            if (cam != null)
                label.transform.rotation = Quaternion.LookRotation(label.transform.position - cam.transform.position);

            string text = ReadValue();
            if (label.text != text) label.text = text;
        }

        string ReadValue()
        {
            switch (kind)
            {
                case SensorBadgeKind.ZoneTemp:
                    if (_temps != null && !string.IsNullOrEmpty(zoneEntityId) &&
                        _temps.Temps.TryGetValue(zoneEntityId, out var t))
                        return $"{ShortZone()}\n{TempUnits.Format(t)}";
                    return $"{ShortZone()}\n—";
                case SensorBadgeKind.AhuLeave:
                    return _ahu != null ? $"SA {_ahu.airLoopName}\n{TempUnits.Format(_ahu.leaveC)}" : "SA\n—";
                case SensorBadgeKind.AhuMix:
                    return _ahu != null ? $"Mix {_ahu.airLoopName}\n{TempUnits.Format(_ahu.mixC)}" : "Mix\n—";
                case SensorBadgeKind.AhuReturn:
                    return _ahu != null ? $"RA {_ahu.airLoopName}\n{TempUnits.Format(_ahu.returnC)}" : "RA\n—";
                case SensorBadgeKind.AhuOa:
                    return _ahu != null ? $"OA {_ahu.airLoopName}\n{TempUnits.Format(_ahu.oatC)}" : "OA\n—";
                case SensorBadgeKind.ChillerStatus:
                    if (_plant != null)
                        return _plant.plantRunning
                            ? $"Chiller\nON { _plant.plantLoad:0.00}"
                            : "Chiller\nOFF";
                    return "Chiller\n—";
                case SensorBadgeKind.TowerStatus:
                    if (_plant != null)
                        return _plant.plantRunning ? "Tower\nON" : "Tower\nOFF";
                    return "Tower\n—";
                default:
                    return "—";
            }
        }

        string ShortZone()
        {
            if (string.IsNullOrEmpty(zoneEntityId)) return "Zone";
            // entity like zone_Floor_3_AHU1 → F3 AHU1
            var parts = zoneEntityId.Replace("zone_", "").Split('_');
            if (parts.Length >= 3)
                return $"F{parts[1]} {parts[2]}";
            return zoneEntityId;
        }
    }
}
