using System;
using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Holds latest multi-target twin I/O from Flask predict (facility + AHU/plant/zones).
    /// Sensor badges and AHU/plant displays read from here when HasLiveData.
    /// </summary>
    public class TwinIoHub : MonoBehaviour
    {
        public static TwinIoHub Instance { get; private set; }

        public bool HasLiveData { get; private set; }
        public TwinIoPayload last;

        void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(this);
                return;
            }
            Instance = this;
        }

        public void Apply(TwinIoPayload io)
        {
            if (io == null) return;
            last = io;
            HasLiveData = true;
            PushToDisplays();
        }

        public void Clear()
        {
            HasLiveData = false;
        }

        void PushToDisplays()
        {
            if (!HasLiveData || last == null) return;

            foreach (var ahu in FindObjectsByType<AhuAirTempDisplay>())
            {
                if (ahu.isAhu2 || string.Equals(ahu.airLoopName, "VAV Sys 2", StringComparison.OrdinalIgnoreCase))
                {
                    ahu.leaveC = last.ahu2_dat_c;
                    ahu.mixC = last.ahu2_mix_c;
                    ahu.returnC = last.ahu2_ra_c;
                    ahu.oatC = last.ahu2_oa_c > 0.01f ? last.ahu2_oa_c : last.oat_c;
                }
                else
                {
                    ahu.leaveC = last.ahu1_dat_c;
                    ahu.mixC = last.ahu1_mix_c;
                    ahu.returnC = last.ahu1_ra_c;
                    ahu.oatC = last.ahu1_oa_c > 0.01f ? last.ahu1_oa_c : last.oat_c;
                }
                ahu.RefreshLabel();
            }

            var temps = FindAnyObjectByType<ZoneTempController>();
            if (temps != null)
                temps.ApplyTwinIoMeans(last.zone_temp_ahu1_mean_c, last.zone_temp_ahu2_mean_c);
        }

        public static TwinIoHub Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("TwinIoHub");
            return go.AddComponent<TwinIoHub>();
        }
    }

    [Serializable]
    public class TwinIoPayload
    {
        public float facility_kw;
        public float cooling_kw;
        public float oat_c;
        public float zone_temp_ahu1_mean_c;
        public float zone_temp_ahu2_mean_c;
        public float max_zone_temp_c;
        public float ahu1_dat_c;
        public float ahu1_mix_c;
        public float ahu1_ra_c;
        public float ahu1_oa_c;
        public float ahu1_fan_plr;
        public float ahu1_oa_frac;
        public float ahu2_dat_c;
        public float ahu2_mix_c;
        public float ahu2_ra_c;
        public float ahu2_oa_c;
        public float ahu2_fan_plr;
        public float ahu2_oa_frac;
        public float chw_supply_c;
        public float chw_return_c;
        public float chw_pump_plr;
        public float cw_pump_plr;
        public float tower_fan_plr;
        public float tower_leaving_c;
    }
}
