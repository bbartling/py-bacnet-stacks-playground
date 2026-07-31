using System.Collections.Generic;
using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Manhattan (90°) MEP runs: stubs out of ports, axis-aligned legs, elbow fittings.
    /// </summary>
    public static class OrthoMepRouter
    {
        public enum AxisOrder
        {
            /// <summary>Y then X then Z — good for risers / zone laterals.</summary>
            YXZ,
            /// <summary>X then Z then Y — good for roof laterals at constant height.</summary>
            XZY,
            /// <summary>Z then X then Y.</summary>
            ZXY,
        }

        /// <summary>Build consecutive orthogonal legs through <paramref name="points"/>.</summary>
        public static List<Vector3[]> Run(
            Transform parent,
            string name,
            IList<Vector3> points,
            float width,
            Material mat,
            bool tagPlantPipe = false)
        {
            var segments = new List<Vector3[]>();
            if (points == null || points.Count < 2) return segments;

            var pathRoot = new GameObject(name);
            pathRoot.transform.SetParent(parent, false);

            for (int i = 0; i < points.Count - 1; i++)
            {
                var a = points[i];
                var b = points[i + 1];
                if (Vector3.Distance(a, b) < 0.05f) continue;
                Seg(pathRoot.transform, $"{name}_L{i}", a, b, width, mat);
                segments.Add(new[] { a, b });
                // Elbow at interior corners
                if (i > 0)
                    Elbow(pathRoot.transform, $"{name}_E{i}", a, width * 1.15f, mat);
            }

            if (tagPlantPipe)
            {
                var pe = pathRoot.GetComponent<TwinEntity>() ?? pathRoot.AddComponent<TwinEntity>();
                pe.entityId = name.ToLowerInvariant();
                pe.entityType = "plant_pipe";
                pe.displayName = name;
                pe.isDemoProxy = true;
            }
            return segments;
        }

        /// <summary>
        /// Stub along from-port forward, Manhattan midpoints to near to-port, stub into to-port.
        /// Port transforms: position = flange, forward = outward normal.
        /// </summary>
        public static List<Vector3[]> PathStubThenOrtho(
            Transform parent,
            string name,
            Transform fromPort,
            Transform toPort,
            float width,
            Material mat,
            float stubLen = 0.55f,
            AxisOrder order = AxisOrder.YXZ,
            bool tagPlantPipe = false)
        {
            Vector3 a = fromPort != null ? fromPort.position : Vector3.zero;
            Vector3 b = toPort != null ? toPort.position : a + Vector3.forward;
            Vector3 aOut = fromPort != null ? fromPort.forward : Vector3.forward;
            Vector3 bOut = toPort != null ? toPort.forward : -Vector3.forward;

            Vector3 afterStub = a + aOut.normalized * stubLen;
            Vector3 beforeStub = b + bOut.normalized * stubLen;

            var pts = new List<Vector3> { a, afterStub };
            AppendManhattan(pts, afterStub, beforeStub, order);
            if (Vector3.Distance(pts[pts.Count - 1], beforeStub) > 0.05f)
                pts.Add(beforeStub);
            pts.Add(b);
            Dedup(pts);
            return Run(parent, name, pts, width, mat, tagPlantPipe);
        }

        /// <summary>Ortho path between two world points (no stubs).</summary>
        public static List<Vector3[]> PathOrtho(
            Transform parent,
            string name,
            Vector3 from,
            Vector3 to,
            float width,
            Material mat,
            AxisOrder order = AxisOrder.YXZ,
            bool tagPlantPipe = false)
        {
            var pts = new List<Vector3> { from };
            AppendManhattan(pts, from, to, order);
            if (Vector3.Distance(pts[pts.Count - 1], to) > 0.05f)
                pts.Add(to);
            Dedup(pts);
            return Run(parent, name, pts, width, mat, tagPlantPipe);
        }

        /// <summary>Vertical riser (already orthographic).</summary>
        public static List<Vector3[]> Riser(
            Transform parent,
            string name,
            Vector3 xz,
            float y0,
            float y1,
            float width,
            Material mat)
        {
            var a = new Vector3(xz.x, y0, xz.z);
            var b = new Vector3(xz.x, y1, xz.z);
            return Run(parent, name, new[] { a, b }, width, mat);
        }

        static void AppendManhattan(List<Vector3> pts, Vector3 from, Vector3 to, AxisOrder order)
        {
            Vector3 cur = from;
            void Step(Vector3 next)
            {
                if (Vector3.Distance(cur, next) < 0.05f) return;
                pts.Add(next);
                cur = next;
            }

            switch (order)
            {
                case AxisOrder.XZY:
                    Step(new Vector3(to.x, cur.y, cur.z));
                    Step(new Vector3(to.x, cur.y, to.z));
                    Step(new Vector3(to.x, to.y, to.z));
                    break;
                case AxisOrder.ZXY:
                    Step(new Vector3(cur.x, cur.y, to.z));
                    Step(new Vector3(to.x, cur.y, to.z));
                    Step(new Vector3(to.x, to.y, to.z));
                    break;
                default: // YXZ
                    Step(new Vector3(cur.x, to.y, cur.z));
                    Step(new Vector3(to.x, to.y, cur.z));
                    Step(new Vector3(to.x, to.y, to.z));
                    break;
            }
        }

        static void Dedup(List<Vector3> pts)
        {
            for (int i = pts.Count - 1; i > 0; i--)
            {
                if (Vector3.Distance(pts[i], pts[i - 1]) < 0.05f)
                    pts.RemoveAt(i);
            }
        }

        public static void Seg(Transform parent, string name, Vector3 a, Vector3 b, float width, Material mat)
        {
            float len = Vector3.Distance(a, b);
            if (len < 0.05f) return;
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.position = (a + b) * 0.5f;
            go.transform.localScale = new Vector3(width, width, len);
            go.transform.rotation = Quaternion.LookRotation((b - a).normalized, Vector3.up);
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
        }

        static void Elbow(Transform parent, string name, Vector3 at, float size, Material mat)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.position = at;
            go.transform.localScale = Vector3.one * size;
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
        }

        /// <summary>Find named port under root, or create a temporary world pose.</summary>
        public static Transform ResolvePort(Transform equipmentRoot, string portName, Vector3 worldFallback, Vector3 outwardFallback)
        {
            if (equipmentRoot != null)
            {
                var t = equipmentRoot.Find(portName);
                if (t != null) return t;
                foreach (var c in equipmentRoot.GetComponentsInChildren<Transform>())
                {
                    if (c.name == portName) return c;
                }
            }
            var go = new GameObject(portName + "_Fallback");
            go.transform.position = worldFallback;
            if (outwardFallback.sqrMagnitude > 1e-6f)
                go.transform.rotation = Quaternion.LookRotation(outwardFallback.normalized, Vector3.up);
            return go.transform;
        }

        public static Transform MakePort(Transform parent, string name, Vector3 localPos, Vector3 localForward)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = Quaternion.LookRotation(localForward.normalized, Vector3.up);
            return go.transform;
        }
    }
}
