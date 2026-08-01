using System.Collections.Generic;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Three Excel-style sensor boards. All sheets share ONE world rotation
    /// (identity) and sit on a clear apron EAST of the massing so hanging
    /// rows never pierce the building. Scene Play auto-rebuilds via
    /// <see cref="TwinSheetKitBootstrap"/>.
    /// </summary>
    public static class SensorBadgeFactory
    {
        const float RowPitch = 1.65f;
        const float ColPoint = 0f;
        const float ColValue = 8f;
        const float SheetGapZ = 18f;
        /// <summary>Meters past the east facade (max X).</summary>
        const float EastClear = 22f;
        const float BoardLift = 6f;

        /// <summary>Locked facing for every sheet — yaw +90° so boards read from the east apron.</summary>
        public static readonly Quaternion SharedSheetRotation = Quaternion.Euler(0f, 90f, 0f);

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Spawn Sensor Badge Kit")]
        public static void MenuSpawn()
        {
            SpawnKit();
            EditorUtility.SetDirty(GameObject.Find("TwinSensorBadges"));
        }

        [MenuItem("Vibe21/Twin/Reseat Sheets Behind Building")]
        public static void MenuReseat()
        {
            SpawnKit();
            Debug.Log("SensorBadgeFactory: rebuilt 3 sheets — shared identity rotation, east apron");
        }
#endif

        public static GameObject SpawnKit()
        {
            void Kill(GameObject go)
            {
                if (go == null) return;
                if (Application.isPlaying) Object.Destroy(go);
                else Object.DestroyImmediate(go);
            }

            Kill(GameObject.Find("TwinSensorBadges"));
            foreach (var name in new[]
                     {
                         "Sheet_AHU1_VAV_Sys1", "Sheet_AHU2_VAV_Sys2", "Sheet_Chiller_Plant",
                         "RoofReadVantage", "SheetReadVantage", "~TwinSheetKitBootstrapRunner"
                     })
                Kill(GameObject.Find(name));

            // Purge orphaned spreadsheet rows from prior broken kits
            foreach (var badge in Object.FindObjectsByType<SensorBadge>(FindObjectsSortMode.None))
            {
                if (badge != null && badge.layout == SensorBadgeLayout.SpreadsheetRow)
                    Kill(badge.gameObject);
            }

            var root = new GameObject("TwinSensorBadges");
            root.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            var boot = root.AddComponent<TwinSheetKitBootstrap>();
            boot.builtByFactory = true;

            Bounds bldg = ComputeBuildingBounds();
            CollectZones(out var ahu1Zones, out var ahu2Zones);

            // East apron: past max X. Arrange boards along Z. All identity rotation.
            float boardY = bldg.max.y + BoardLift;
            float apronX = bldg.max.x + EastClear;
            float midZ = bldg.center.z;

            BuildAhuSheet(root.transform, "Sheet_AHU1_VAV_Sys1",
                new Vector3(apronX, boardY, midZ - SheetGapZ),
                "AHU 1  ·  VAV Sys 1", "VAV Sys 1", false, ahu1Zones);

            BuildPlantSheet(root.transform, "Sheet_Chiller_Plant",
                new Vector3(apronX, boardY, midZ),
                "CHILLER / TOWER  ·  plant I/O");

            BuildAhuSheet(root.transform, "Sheet_AHU2_VAV_Sys2",
                new Vector3(apronX, boardY, midZ + SheetGapZ),
                "AHU 2  ·  VAV Sys 2", "VAV Sys 2", true, ahu2Zones);

            var stand = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            stand.name = "SheetReadVantage";
            stand.transform.SetParent(root.transform, false);
            stand.transform.SetPositionAndRotation(
                new Vector3(apronX + 8f, bldg.min.y + 0.05f, midZ),
                Quaternion.identity);
            stand.transform.localScale = new Vector3(2.4f, 0.05f, 2.4f);
            var sm = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            var sc = new Color(0.2f, 0.55f, 0.75f, 1f);
            sm.color = sc;
            if (sm.HasProperty("_BaseColor")) sm.SetColor("_BaseColor", sc);
            stand.GetComponent<MeshRenderer>().sharedMaterial = sm;
            Object.DestroyImmediate(stand.GetComponent<Collider>());

            Debug.Log(
                $"SensorBadgeFactory: sheets @ x={apronX:0.0} y={boardY:0.0} rot=identity " +
                $"(clear of bldg maxX={bldg.max.x:0.0})");
            return root;
        }

        static void CollectZones(out List<TwinEntity> ahu1, out List<TwinEntity> ahu2)
        {
            ahu1 = new List<TwinEntity>();
            ahu2 = new List<TwinEntity>();
            foreach (var te in Object.FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone") continue;
                var dn = te.displayName ?? "";
                if (dn.Contains("AHU2")) ahu2.Add(te);
                else ahu1.Add(te);
            }
            ahu1.Sort((a, b) => string.CompareOrdinal(a.displayName, b.displayName));
            ahu2.Sort((a, b) => string.CompareOrdinal(a.displayName, b.displayName));
        }

        static void BuildAhuSheet(
            Transform parent, string name, Vector3 worldPos,
            string sheetTitle, string airLoop, bool ahu2, List<TwinEntity> zones)
        {
            int rows = 1 + zones.Count + 1 + 7;
            var sheet = MakeSheetPanel(parent, name, worldPos, sheetTitle, rows);
            int r = 0;
            AddHeaderRow(sheet, r++, "POINT", "READING");
            foreach (var z in zones)
                AddRow(sheet, r++, SensorBadgeKind.ZoneTemp, z.entityId, airLoop, ahu2);
            AddSectionRow(sheet, r++, "— AHU I/O —");
            AddRow(sheet, r++, SensorBadgeKind.AhuZoneMean, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuOa, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuMix, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuReturn, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuLeave, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuFanPlr, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuOaFrac, null, airLoop, ahu2);
        }

        static void BuildPlantSheet(Transform parent, string name, Vector3 worldPos, string sheetTitle)
        {
            var sheet = MakeSheetPanel(parent, name, worldPos, sheetTitle, 13);
            int r = 0;
            AddHeaderRow(sheet, r++, "POINT", "READING");
            AddSectionRow(sheet, r++, "— CHILLER / TOWER I/O —");
            AddRow(sheet, r++, SensorBadgeKind.Oat, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.FacilityKw, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.CoolingKw, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.ChillerStatus, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.TowerStatus, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.ChwSupply, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.ChwReturn, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.ChwPumpPlr, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.CwPumpPlr, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.TowerFanPlr, null, null, false);
            AddRow(sheet, r++, SensorBadgeKind.TowerLeaving, null, null, false);
        }

        static Transform MakeSheetPanel(
            Transform parent, string name, Vector3 worldPos, string sheetTitle, int dataRows)
        {
            var sheet = new GameObject(name);
            sheet.transform.SetParent(parent, false);
            // Force world identity — never inherit a look-at yaw
            sheet.transform.SetPositionAndRotation(worldPos, SharedSheetRotation);
            sheet.AddComponent<TwinSheetRotationLock>();

            var handle = GameObject.CreatePrimitive(PrimitiveType.Cube);
            handle.name = "SheetGrabHandle";
            handle.transform.SetParent(sheet.transform, false);
            handle.transform.localPosition = Vector3.zero;
            handle.transform.localRotation = Quaternion.identity;
            handle.transform.localScale = new Vector3(0.55f, 0.55f, 0.55f);
            var hm = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            var hc = new Color(0.25f, 0.75f, 0.95f, 1f);
            hm.color = hc;
            if (hm.HasProperty("_BaseColor")) hm.SetColor("_BaseColor", hc);
            handle.GetComponent<MeshRenderer>().sharedMaterial = hm;

            var titleGo = new GameObject("SheetTitle");
            titleGo.transform.SetParent(sheet.transform, false);
            titleGo.transform.localPosition = new Vector3(0f, 1.0f, 0f);
            titleGo.transform.localRotation = Quaternion.identity;
            var tm = titleGo.AddComponent<TextMesh>();
            tm.text = sheetTitle;
            tm.characterSize = 0.16f;
            tm.fontSize = 56;
            tm.anchor = TextAnchor.MiddleLeft;
            tm.alignment = TextAlignment.Left;
            tm.color = new Color(0.92f, 0.98f, 0.95f);

            var content = new GameObject("Rows");
            content.transform.SetParent(sheet.transform, false);
            content.transform.localPosition = new Vector3(0f, -0.5f, 0f);
            content.transform.localRotation = Quaternion.identity;
            return content.transform;
        }

        static void AddHeaderRow(Transform rowsRoot, int row, string a, string b)
        {
            var go = new GameObject($"Header_{row}");
            go.transform.SetParent(rowsRoot, false);
            go.transform.localPosition = new Vector3(0f, -row * RowPitch, 0f);
            go.transform.localRotation = Quaternion.identity;
            MakeCellText(go.transform, "H_Point", new Vector3(ColPoint, 0f, 0f), a,
                new Color(0.55f, 0.9f, 0.75f), true);
            MakeCellText(go.transform, "H_Value", new Vector3(ColValue, 0f, 0f), b,
                new Color(0.55f, 0.9f, 0.75f), true);
        }

        static void AddSectionRow(Transform rowsRoot, int row, string text)
        {
            var go = new GameObject($"Section_{row}");
            go.transform.SetParent(rowsRoot, false);
            go.transform.localPosition = new Vector3(0f, -row * RowPitch, 0f);
            go.transform.localRotation = Quaternion.identity;
            MakeCellText(go.transform, "Section", new Vector3(ColPoint, 0f, 0f), text,
                new Color(0.85f, 0.78f, 0.45f), true);
        }

        static void AddRow(
            Transform rowsRoot, int row, SensorBadgeKind kind,
            string zoneId, string airLoop, bool ahu2)
        {
            var go = new GameObject($"Row_{row}_{kind}");
            go.transform.SetParent(rowsRoot, false);
            go.transform.localPosition = new Vector3(0f, -row * RowPitch, 0f);
            go.transform.localRotation = Quaternion.identity;

            var titleGo = new GameObject("Title");
            titleGo.transform.SetParent(go.transform, false);
            titleGo.transform.localRotation = Quaternion.identity;
            var titleTm = titleGo.AddComponent<TextMesh>();

            var valueGo = new GameObject("Value");
            valueGo.transform.SetParent(go.transform, false);
            valueGo.transform.localRotation = Quaternion.identity;
            var valueTm = valueGo.AddComponent<TextMesh>();

            var badge = go.AddComponent<SensorBadge>();
            badge.kind = kind;
            badge.layout = SensorBadgeLayout.SpreadsheetRow;
            badge.zoneEntityId = zoneId;
            badge.airLoopName = airLoop ?? "VAV Sys 1";
            badge.isAhu2 = ahu2;
            badge.titleLabel = titleTm;
            badge.valueLabel = valueTm;
            badge.spreadsheetColGap = ColValue;
            badge.EnsureSplitLabels();

            var te = go.AddComponent<TwinEntity>();
            te.entityId = go.name.ToLowerInvariant();
            te.entityType = "sensor_badge";
            te.displayName = go.name;
            te.isDemoProxy = true;
        }

        static TextMesh MakeCellText(Transform parent, string name, Vector3 localPos, string text, Color col, bool boldish)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = Quaternion.identity;
            var tm = go.AddComponent<TextMesh>();
            tm.text = text;
            tm.characterSize = boldish ? 0.12f : 0.11f;
            tm.fontSize = boldish ? 46 : 42;
            tm.anchor = TextAnchor.MiddleLeft;
            tm.alignment = TextAlignment.Left;
            tm.color = col;
            return tm;
        }

        public static Bounds ComputeBuildingBounds()
        {
            var bounds = new Bounds(Vector3.zero, Vector3.one);
            bool any = false;
            var massing = GameObject.Find("Liberty100Massing");
            if (massing != null)
            {
                foreach (var r in massing.GetComponentsInChildren<Renderer>())
                {
                    if (!any) { bounds = r.bounds; any = true; }
                    else bounds.Encapsulate(r.bounds);
                }
            }
            if (!any)
            {
                foreach (var te in Object.FindObjectsByType<TwinEntity>())
                {
                    if (te.entityType != "zone") continue;
                    foreach (var r in te.GetComponentsInChildren<Renderer>())
                    {
                        if (!any) { bounds = r.bounds; any = true; }
                        else bounds.Encapsulate(r.bounds);
                    }
                }
            }
            if (!any)
                bounds = new Bounds(new Vector3(28f, 12f, 19f), new Vector3(40f, 24f, 30f));
            return bounds;
        }
    }

    /// <summary>Every LateUpdate: force this sheet to the shared kit rotation.</summary>
    public class TwinSheetRotationLock : MonoBehaviour
    {
        void LateUpdate()
        {
            if (transform.rotation != SensorBadgeFactory.SharedSheetRotation)
                transform.rotation = SensorBadgeFactory.SharedSheetRotation;
            // Keep local rot of direct text children identity (no drifted pitch/yaw)
            for (int i = 0; i < transform.childCount; i++)
            {
                var c = transform.GetChild(i);
                if (c.name == "SheetGrabHandle") continue;
                if (c.localRotation != Quaternion.identity)
                    c.localRotation = Quaternion.identity;
            }
        }
    }

    /// <summary>
    /// On Play, destroy the broken scene kit and rebuild with shared rotation.
    /// Attach to TwinSensorBadges (factory adds this automatically).
    /// </summary>
    public class TwinSheetKitBootstrap : MonoBehaviour
    {
        [Tooltip("Set by factory after a clean rebuild; clears so we don't loop.")]
        public bool builtByFactory;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void AutoReseatOnPlay()
        {
            if (!Application.isPlaying) return;
            // Defer one frame so massing renderers exist
            var runner = new GameObject("~TwinSheetKitBootstrapRunner");
            runner.hideFlags = HideFlags.HideAndDontSave;
            runner.AddComponent<TwinSheetKitBootstrapRunner>();
        }
    }

    class TwinSheetKitBootstrapRunner : MonoBehaviour
    {
        void Start()
        {
            SensorBadgeFactory.SpawnKit();
            Destroy(gameObject);
        }
    }
}
