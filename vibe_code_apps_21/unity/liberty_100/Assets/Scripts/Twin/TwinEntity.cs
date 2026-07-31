using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Stable backend binding for Twin entities (zones, AHUs, proxies).</summary>
    public class TwinEntity : MonoBehaviour
    {
        public string entityId;
        public string entityType; // zone | ahu_proxy | sensor_proxy | surface
        public string displayName;
        public bool isDemoProxy;
    }
}
