using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Spawns a kit of placeable sensor badges (zone / AHU / plant) for manual Editor layout.
    /// </summary>
    public static class SensorBadgeFactory
    {
#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Spawn Sensor Badge Kit")]
        public static void MenuSpawn()
        {
            SpawnKit();
        }
#endif

        public static GameObject SpawnKit()
        {
            var old = GameObject.Find("TwinSensorBadges");
            if (old != null)
            {
                if (Application.isPlaying) Object.Destroy(old);
                else Object.DestroyImmediate(old);
            }

            var root = new GameObject("TwinSensorBadges");
            float y = 28f;
            float x = 5f;
            int col = 0;
            int row = 0;

            // Zone badges
            foreach (var te in Object.FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone") continue;
                var pos = new Vector3(x + col * 2.2f, y + row * 1.4f, -40f);
                MakeBadge(root.transform, $"Badge_Zone_{te.entityId}", pos,
                    SensorBadgeKind.ZoneTemp, new Color(0.35f, 0.75f, 0.95f),
                    zoneId: te.entityId);
                col++;
                if (col >= 6) { col = 0; row++; }
            }

            // AHU points — Sys 1 & 2
            float ax = 58f;
            SpawnAhuSet(root.transform, "VAV Sys 1", false, new Vector3(ax, y, -40f));
            SpawnAhuSet(root.transform, "VAV Sys 2", true, new Vector3(ax + 8f, y, -40f));

            // Plant
            MakeBadge(root.transform, "Badge_Chiller", new Vector3(ax + 18f, y, -40f),
                SensorBadgeKind.ChillerStatus, new Color(0.3f, 0.55f, 0.95f));
            MakeBadge(root.transform, "Badge_Tower", new Vector3(ax + 21f, y, -40f),
                SensorBadgeKind.TowerStatus, new Color(0.4f, 0.85f, 0.8f));

            Debug.Log("SensorBadgeFactory: TwinSensorBadges kit spawned — drag badges in Scene view");
            return root;
        }

        static void SpawnAhuSet(Transform parent, string loop, bool ahu2, Vector3 origin)
        {
            MakeBadge(parent, $"Badge_{loop}_OA", origin + new Vector3(0f, 0f, 0f),
                SensorBadgeKind.AhuOa, new Color(0.4f, 0.85f, 0.5f), airLoop: loop, ahu2: ahu2);
            MakeBadge(parent, $"Badge_{loop}_Mix", origin + new Vector3(0f, 1.3f, 0f),
                SensorBadgeKind.AhuMix, new Color(0.9f, 0.88f, 0.55f), airLoop: loop, ahu2: ahu2);
            MakeBadge(parent, $"Badge_{loop}_RA", origin + new Vector3(0f, 2.6f, 0f),
                SensorBadgeKind.AhuReturn, new Color(1f, 0.55f, 0.35f), airLoop: loop, ahu2: ahu2);
            MakeBadge(parent, $"Badge_{loop}_SA", origin + new Vector3(0f, 3.9f, 0f),
                SensorBadgeKind.AhuLeave, new Color(0.45f, 0.7f, 1f), airLoop: loop, ahu2: ahu2);
        }

        static GameObject MakeBadge(
            Transform parent,
            string name,
            Vector3 worldPos,
            SensorBadgeKind kind,
            Color iconColor,
            string zoneId = null,
            string airLoop = null,
            bool ahu2 = false)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.position = worldPos;

            // Diamond / icon
            var icon = GameObject.CreatePrimitive(PrimitiveType.Cube);
            icon.name = "Icon";
            icon.transform.SetParent(go.transform, false);
            icon.transform.localScale = new Vector3(0.55f, 0.55f, 0.12f);
            icon.transform.localRotation = Quaternion.Euler(0f, 0f, 45f);
            var mat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            mat.color = iconColor;
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", iconColor);
            icon.GetComponent<MeshRenderer>().sharedMaterial = mat;
            Object.DestroyImmediate(icon.GetComponent<Collider>());

            var labelGo = new GameObject("Label");
            labelGo.transform.SetParent(go.transform, false);
            labelGo.transform.localPosition = new Vector3(0f, 0.85f, 0f);
            var tm = labelGo.AddComponent<TextMesh>();
            tm.characterSize = 0.12f;
            tm.fontSize = 48;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = Color.white;
            tm.text = name;

            var badge = go.AddComponent<SensorBadge>();
            badge.kind = kind;
            badge.zoneEntityId = zoneId;
            badge.airLoopName = airLoop ?? "VAV Sys 1";
            badge.isAhu2 = ahu2;
            badge.label = tm;
            badge.icon = icon.GetComponent<MeshRenderer>();

            var te = go.AddComponent<TwinEntity>();
            te.entityId = name.ToLowerInvariant();
            te.entityType = "sensor_badge";
            te.displayName = name;
            te.isDemoProxy = true;

            return go;
        }
    }
}
