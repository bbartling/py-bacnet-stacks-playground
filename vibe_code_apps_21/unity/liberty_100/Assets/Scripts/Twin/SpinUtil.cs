using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Spin helpers. Prefer SpinLocalY for procedural SpinPivots.</summary>
    public static class SpinUtil
    {
        public static void SpinWorldUp(Transform t, float degrees)
        {
            if (t == null) return;
            t.RotateAround(t.position, Vector3.up, degrees);
        }

        /// <summary>Spin around transform local Y — correct for SpinPivot fans/props.</summary>
        public static void SpinLocalY(Transform t, float degrees)
        {
            if (t == null) return;
            t.Rotate(0f, degrees, 0f, Space.Self);
        }

        /// <summary>
        /// Spin a disk around its thin axis using lossyScale-adjusted extents.
        /// Prefer SpinLocalY when a SpinPivot is available.
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
                var ls = t.lossyScale;
                float sx = Mathf.Abs(e.x * ls.x);
                float sy = Mathf.Abs(e.y * ls.y);
                float sz = Mathf.Abs(e.z * ls.z);
                if (sx <= sy && sx <= sz) return t.TransformDirection(Vector3.right).normalized;
                if (sy <= sx && sy <= sz) return t.TransformDirection(Vector3.up).normalized;
                return t.TransformDirection(Vector3.forward).normalized;
            }
            return t.right;
        }
    }
}
