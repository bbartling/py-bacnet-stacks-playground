using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Cartoon drone mesh that follows the free-fly camera with spinning props.</summary>
    public class DroneVisualBob : MonoBehaviour
    {
        public Transform follow;
        public Vector3 localOffset = new Vector3(0.8f, -0.35f, 1.2f);
        public float bobAmp = 0.08f;
        public float bobHz = 1.6f;
        public Transform[] props;
        public float propRpm = 900f;

        void LateUpdate()
        {
            var cam = follow != null ? follow : (Camera.main != null ? Camera.main.transform : null);
            if (cam == null) return;
            float bob = Mathf.Sin(Time.time * Mathf.PI * 2f * bobHz) * bobAmp;
            transform.position = cam.TransformPoint(localOffset + Vector3.up * bob);
            transform.rotation = Quaternion.Slerp(transform.rotation, cam.rotation, 0.15f);
            if (props == null) return;
            float deg = propRpm * 6f * Time.deltaTime;
            foreach (var p in props)
            {
                if (p != null) p.Rotate(Vector3.up, deg, Space.Self);
            }
        }
    }
}
