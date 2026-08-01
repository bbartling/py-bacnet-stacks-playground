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
        AhuFanPlr,
        AhuOaFrac,
        AhuZoneMean,
        ChillerStatus,
        TowerStatus,
        ChwSupply,
        ChwReturn,
        ChwPumpPlr,
        CwPumpPlr,
        TowerFanPlr,
        TowerLeaving,
        FacilityKw,
        CoolingKw,
        Oat
    }

    public enum SensorBadgeLayout
    {
        /// <summary>Title above value (default icon badge).</summary>
        Stacked,
        /// <summary>Title left, value right — spreadsheet row.</summary>
        SpreadsheetRow
    }

    /// <summary>
    /// Manually placeable sensor icon + live reading (no LOS occlusion).
    /// </summary>
    public class SensorBadge : MonoBehaviour
    {
        public SensorBadgeKind kind = SensorBadgeKind.ZoneTemp;
        public SensorBadgeLayout layout = SensorBadgeLayout.Stacked;
        public string zoneEntityId;
        public string airLoopName = "VAV Sys 1";
        public bool isAhu2;
        public TextMesh label;
        public TextMesh titleLabel;
        public TextMesh valueLabel;
        public Renderer icon;
        public float titleValueGap = 0.55f;
        /// <summary>Horizontal gap for spreadsheet rows (title → value).</summary>
        public float spreadsheetColGap = 4.2f;

        ZoneTempController _temps;
        AhuAirTempDisplay _ahu;
        PlantVisualController _plant;

        void Start()
        {
            _temps = FindAnyObjectByType<ZoneTempController>();
            EnsureSplitLabels();
            RefreshBindings();
        }

        public void EnsureSplitLabels()
        {
            if (titleLabel != null && valueLabel != null)
            {
                ApplyLayoutOffsets();
                return;
            }

            if (label != null && titleLabel == null)
            {
                titleLabel = label;
                label = null;
            }

            if (titleLabel == null)
            {
                var go = new GameObject("Title");
                go.transform.SetParent(transform, false);
                titleLabel = go.AddComponent<TextMesh>();
            }

            if (valueLabel == null)
            {
                var go = new GameObject("Value");
                go.transform.SetParent(transform, false);
                valueLabel = go.AddComponent<TextMesh>();
            }

            ApplyLayoutOffsets();
            StyleTitle(titleLabel, layout);
            StyleValue(valueLabel, layout);
        }

        public void ApplyLayoutOffsets()
        {
            if (titleLabel == null || valueLabel == null) return;
            if (layout == SensorBadgeLayout.SpreadsheetRow)
            {
                titleLabel.transform.localPosition = new Vector3(0f, 0f, 0f);
                valueLabel.transform.localPosition = new Vector3(spreadsheetColGap, 0f, 0f);
                titleLabel.anchor = TextAnchor.MiddleLeft;
                titleLabel.alignment = TextAlignment.Left;
                valueLabel.anchor = TextAnchor.MiddleLeft;
                valueLabel.alignment = TextAlignment.Left;
            }
            else
            {
                titleLabel.transform.localPosition = new Vector3(0f, titleValueGap * 0.55f + 0.35f, 0f);
                valueLabel.transform.localPosition = new Vector3(0f, -titleValueGap * 0.35f, 0f);
                titleLabel.anchor = TextAnchor.LowerCenter;
                titleLabel.alignment = TextAlignment.Center;
                valueLabel.anchor = TextAnchor.UpperCenter;
                valueLabel.alignment = TextAlignment.Center;
            }
        }

        static void StyleTitle(TextMesh tm, SensorBadgeLayout layout)
        {
            tm.characterSize = layout == SensorBadgeLayout.SpreadsheetRow ? 0.16f : 0.11f;
            tm.fontSize = layout == SensorBadgeLayout.SpreadsheetRow ? 56 : 52;
            tm.color = new Color(0.88f, 0.92f, 0.96f);
            tm.lineSpacing = 1.2f;
        }

        static void StyleValue(TextMesh tm, SensorBadgeLayout layout)
        {
            tm.characterSize = layout == SensorBadgeLayout.SpreadsheetRow ? 0.18f : 0.13f;
            tm.fontSize = layout == SensorBadgeLayout.SpreadsheetRow ? 60 : 56;
            tm.color = Color.white;
            tm.lineSpacing = 1.2f;
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
            EnsureSplitLabels();

            // Spreadsheet rows: stay glued to parent sheet (no billboard, no world drift)
            if (layout == SensorBadgeLayout.SpreadsheetRow)
            {
                if (titleLabel != null)
                {
                    titleLabel.transform.localRotation = Quaternion.identity;
                    titleLabel.transform.localPosition = new Vector3(0f, 0f, 0f);
                }
                if (valueLabel != null)
                {
                    valueLabel.transform.localRotation = Quaternion.identity;
                    valueLabel.transform.localPosition = new Vector3(spreadsheetColGap, 0f, 0f);
                }
            }
            else
            {
                var cam = Camera.main;
                if (cam != null)
                {
                    Face(titleLabel, cam);
                    Face(valueLabel, cam);
                    if (label != null) Face(label, cam);
                }
            }

            ReadValue(out string title, out string value);
            if (titleLabel != null && titleLabel.text != title) titleLabel.text = title;
            if (valueLabel != null && valueLabel.text != value) valueLabel.text = value;
        }

        static void Face(TextMesh tm, Camera cam)
        {
            if (tm == null) return;
            tm.transform.rotation = Quaternion.LookRotation(tm.transform.position - cam.transform.position);
        }

        void ReadValue(out string title, out string value)
        {
            var hub = TwinIoHub.Instance;
            bool live = hub != null && hub.HasLiveData && hub.last != null;
            var io = live ? hub.last : null;

            switch (kind)
            {
                case SensorBadgeKind.ZoneTemp:
                    title = ShortZone();
                    if (_temps != null && !string.IsNullOrEmpty(zoneEntityId) &&
                        _temps.Temps.TryGetValue(zoneEntityId, out var t))
                        value = TempUnits.Format(t);
                    else
                        value = "—";
                    return;
                case SensorBadgeKind.AhuZoneMean:
                    title = isAhu2 ? "Zones mean (AHU2)" : "Zones mean (AHU1)";
                    if (live)
                        value = TempUnits.Format(isAhu2 ? io.zone_temp_ahu2_mean_c : io.zone_temp_ahu1_mean_c);
                    else
                        value = "—";
                    return;
                case SensorBadgeKind.AhuLeave:
                    title = "SA (DAT)";
                    if (live)
                        value = TempUnits.Format(isAhu2 ? io.ahu2_dat_c : io.ahu1_dat_c);
                    else
                        value = _ahu != null ? TempUnits.Format(_ahu.leaveC) : "—";
                    return;
                case SensorBadgeKind.AhuMix:
                    title = "Mix";
                    if (live)
                        value = TempUnits.Format(isAhu2 ? io.ahu2_mix_c : io.ahu1_mix_c);
                    else
                        value = _ahu != null ? TempUnits.Format(_ahu.mixC) : "—";
                    return;
                case SensorBadgeKind.AhuReturn:
                    title = "RA (return)";
                    if (live)
                        value = TempUnits.Format(isAhu2 ? io.ahu2_ra_c : io.ahu1_ra_c);
                    else
                        value = _ahu != null ? TempUnits.Format(_ahu.returnC) : "—";
                    return;
                case SensorBadgeKind.AhuOa:
                    title = "OA";
                    if (live)
                    {
                        float oa = isAhu2 ? io.ahu2_oa_c : io.ahu1_oa_c;
                        if (oa < 0.01f) oa = io.oat_c;
                        value = TempUnits.Format(oa);
                    }
                    else
                        value = _ahu != null ? TempUnits.Format(_ahu.oatC) : "—";
                    return;
                case SensorBadgeKind.AhuFanPlr:
                    title = "Fan PLR";
                    if (live)
                        value = $"{(isAhu2 ? io.ahu2_fan_plr : io.ahu1_fan_plr) * 100f:0}%";
                    else
                        value = "—";
                    return;
                case SensorBadgeKind.AhuOaFrac:
                    title = "OA frac";
                    if (live)
                        value = $"{(isAhu2 ? io.ahu2_oa_frac : io.ahu1_oa_frac) * 100f:0}%";
                    else
                        value = "—";
                    return;
                case SensorBadgeKind.ChillerStatus:
                    title = "Chiller";
                    if (_plant != null)
                        value = _plant.plantRunning ? $"ON  load {_plant.plantLoad:0.00}" : "OFF";
                    else
                        value = "—";
                    return;
                case SensorBadgeKind.TowerStatus:
                    title = "Cooling Tower";
                    if (_plant != null)
                        value = _plant.plantRunning ? "ON" : "OFF";
                    else
                        value = "—";
                    return;
                case SensorBadgeKind.ChwSupply:
                    title = "CHW supply";
                    value = live ? TempUnits.Format(io.chw_supply_c) : "—";
                    return;
                case SensorBadgeKind.ChwReturn:
                    title = "CHW return";
                    value = live ? TempUnits.Format(io.chw_return_c) : "—";
                    return;
                case SensorBadgeKind.ChwPumpPlr:
                    title = "CHW pump PLR";
                    value = live ? $"{io.chw_pump_plr * 100f:0}%" : "—";
                    return;
                case SensorBadgeKind.CwPumpPlr:
                    title = "CW pump PLR";
                    value = live ? $"{io.cw_pump_plr * 100f:0}%" : "—";
                    return;
                case SensorBadgeKind.TowerFanPlr:
                    title = "Tower fan PLR";
                    value = live ? $"{io.tower_fan_plr * 100f:0}%" : "—";
                    return;
                case SensorBadgeKind.TowerLeaving:
                    title = "Tower leaving";
                    value = live ? TempUnits.Format(io.tower_leaving_c) : "—";
                    return;
                case SensorBadgeKind.FacilityKw:
                    title = "Facility kW";
                    value = live ? $"{io.facility_kw:0.0}" : "—";
                    return;
                case SensorBadgeKind.CoolingKw:
                    title = "Cooling kW";
                    value = live ? $"{io.cooling_kw:0.0}" : "—";
                    return;
                case SensorBadgeKind.Oat:
                    title = "OAT";
                    value = live ? TempUnits.Format(io.oat_c) : "—";
                    return;
                default:
                    title = "—";
                    value = "—";
                    return;
            }
        }

        string ShortZone()
        {
            if (string.IsNullOrEmpty(zoneEntityId)) return "Zone";
            var parts = zoneEntityId.Replace("zone_", "").Split('_');
            if (parts.Length >= 3)
                return $"F{parts[1]} zone temp";
            return zoneEntityId;
        }
    }
}
