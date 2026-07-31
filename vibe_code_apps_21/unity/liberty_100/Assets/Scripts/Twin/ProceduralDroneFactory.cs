using System.Collections.Generic;
using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Greyscale procedural quadcopter with airplane-style spinning blades.
    /// SpinPivot local Y = prop spin axis. Root keeps a SphereCollider for bounce.
    /// </summary>
    public static class ProceduralDroneFactory
    {
        public static GameObject Build(Vector3 spawn, Transform parent = null)
        {
            var root = new GameObject("TwinDrone");
            if (parent != null) root.transform.SetParent(parent, false);
            root.transform.position = spawn;
            root.transform.rotation = Quaternion.identity;

            var bodyMat = Mat(new Color(0.45f, 0.45f, 0.48f));
            var armMat = Mat(new Color(0.28f, 0.28f, 0.30f));
            var propMat = Mat(new Color(0.72f, 0.72f, 0.74f));
            var hubMat = Mat(new Color(0.18f, 0.18f, 0.20f));

            var body = GameObject.CreatePrimitive(PrimitiveType.Cube);
            body.name = "Body";
            body.transform.SetParent(root.transform, false);
            body.transform.localScale = new Vector3(0.55f, 0.18f, 0.4f);
            body.GetComponent<MeshRenderer>().sharedMaterial = bodyMat;
            KillCollider(body);

            var cam = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            cam.name = "Cam";
            cam.transform.SetParent(root.transform, false);
            cam.transform.localPosition = new Vector3(0.22f, -0.05f, 0f);
            cam.transform.localScale = Vector3.one * 0.12f;
            cam.GetComponent<MeshRenderer>().sharedMaterial = hubMat;
            KillCollider(cam);

            var spins = new List<Transform>();
            float reach = 0.48f;
            Vector3[] corners =
            {
                new Vector3(reach, 0.06f, reach),
                new Vector3(reach, 0.06f, -reach),
                new Vector3(-reach, 0.06f, reach),
                new Vector3(-reach, 0.06f, -reach),
            };

            for (int i = 0; i < 4; i++)
            {
                var corner = corners[i];
                var arm = GameObject.CreatePrimitive(PrimitiveType.Cube);
                arm.name = $"Arm_{i}";
                arm.transform.SetParent(root.transform, false);
                arm.transform.localPosition = corner * 0.5f;
                arm.transform.localScale = new Vector3(0.08f, 0.05f, reach * 0.95f);
                arm.transform.localRotation = Quaternion.LookRotation(new Vector3(corner.x, 0f, corner.z), Vector3.up);
                arm.GetComponent<MeshRenderer>().sharedMaterial = armMat;
                KillCollider(arm);

                // Airplane-style blades (not flat disc) — spin about local Y / world up
                var pivot = AirplanePropFactory.BuildFacingUp(
                    root.transform, $"SpinPivot_{i}", corner, 0.28f, propMat, blades: 2);
                spins.Add(pivot);
            }

            var te = root.AddComponent<TwinEntity>();
            te.entityId = "drone_player";
            te.entityType = "drone_proxy";
            te.displayName = "Flyable DEMO drone";
            te.isDemoProxy = true;

            var ctrl = root.AddComponent<DroneController>();
            ctrl.rotors = spins.ToArray();
            ctrl.cameraRig = Camera.main != null ? Camera.main.transform : null;
            ctrl.enableMotorSound = true;
            ctrl.motorVolume = 0.45f;
            ctrl.propRpm = 1800f;
            ctrl.verticalSpeed = 22f;
            ctrl.collideRadius = 0.55f;

            if (Camera.main != null)
            {
                var ff = Camera.main.GetComponent<DroneFlyCamera>();
                if (ff != null) ff.enabled = false;
            }

            return root;
        }

        static void KillCollider(GameObject go)
        {
            var c = go.GetComponent<Collider>();
            if (c == null) return;
            if (Application.isPlaying) Object.Destroy(c);
            else Object.DestroyImmediate(c);
        }

        static Material Mat(Color c)
        {
            var m = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            m.color = c;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            return m;
        }
    }
}
