using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Spin a transform around a stable axis (fixes FBX local-axis nonsense).</summary>
    public static class SpinUtil
    {
        /// <summary>World-up spin — correct for drone props.</summary>
        public static void SpinWorldUp(Transform t, float degrees)
        {
            if (t == null) return;
            t.RotateAround(t.position, Vector3.up, degrees);
        }

        /// <summary>
        /// Spin a disk/fan around its thin axis (mesh local). Falls back to local right.
        /// </summary>
        public static void SpinFanDisk(Transform t, float degrees)
        {
            if (t == null) return;
            var axis = GuessDiskAxisWorld(t);
            t.RotateAround(t.position, axis, degrees);
        }

        public static Vector3 GuessDiskAxisWorld(Transform t)
        {
            var mf = t.GetComponentInChildren<MeshFilter>();
            if (mf != null && mf.sharedMesh != null)
            {
                var e = mf.sharedMesh.bounds.extents;
                // Thinnest local extent ≈ disk axis
                if (e.x <= e.y && e.x <= e.z) return t.TransformDirection(Vector3.right).normalized;
                if (e.y <= e.x && e.y <= e.z) return t.TransformDirection(Vector3.up).normalized;
                return t.TransformDirection(Vector3.forward).normalized;
            }
            return t.right;
        }
    }
}
