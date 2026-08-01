using System.Collections.Generic;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Vibe21.Twin
{
    /// <summary>
    /// Spawns giant Excel-style sensor spreadsheets mid-air over the roof —
    /// one sheet per AHU (zones + AHU I/O) and one plant/chiller I/O sheet.
    /// Oriented for a person standing on the roof looking at the boards.
    /// </summary>
    public static class SensorBadgeFactory
    {
        const float RowPitch = 1.05f;
        const float ColPoint = 0f;
        const float ColValue = 5.5f;
        const float SheetWidth = 12f;
        const float HeaderH = 1.4f;
        const float EyeHeight = 1.7f; // standing on roof

#if UNITY_EDITOR
        [MenuItem("Vibe21/Twin/Spawn Sensor Badge Kit")]
        public static void MenuSpawn()
        {
            SpawnKit();
        }

        [MenuItem("Vibe21/Twin/Spread Sensor Badge Labels")]
        public static void MenuSpreadLabels()
        {
            int n = 0;
            foreach (var b in Object.FindObjectsByType<SensorBadge>())
            {
                b.EnsureSplitLabels();
                n++;
            }
            Debug.Log($"SensorBadgeFactory: refreshed {n} badge labels");
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
            Bounds roof = ComputeRoofBounds();
            Vector3 roofStand = new Vector3(roof.center.x, roof.max.y + EyeHeight, roof.center.z);

            var ahu1Zones = new List<TwinEntity>();
            var ahu2Zones = new List<TwinEntity>();
            foreach (var te in Object.FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone") continue;
                var dn = te.displayName ?? "";
                if (dn.Contains("AHU2")) ahu2Zones.Add(te);
                else ahu1Zones.Add(te);
            }
            ahu1Zones.Sort((a, b) => string.CompareOrdinal(a.displayName, b.displayName));
            ahu2Zones.Sort((a, b) => string.CompareOrdinal(a.displayName, b.displayName));

            // Three boards around the standing vantage — like giant monitors on the roof
            float span = Mathf.Max(roof.extents.x, roof.extents.z, 18f) * 0.55f;
            float boardY = roof.max.y + 4.5f; // mid-air above roof deck

            // Facing inward toward roofStand
            BuildAhuSheet(root.transform, "Sheet_AHU1_VAV_Sys1",
                new Vector3(roof.center.x - span, boardY, roof.center.z),
                roofStand,
                "AHU 1  ·  VAV Sys 1",
                "VAV Sys 1", false, ahu1Zones);

            BuildAhuSheet(root.transform, "Sheet_AHU2_VAV_Sys2",
                new Vector3(roof.center.x + span, boardY, roof.center.z),
                roofStand,
                "AHU 2  ·  VAV Sys 2",
                "VAV Sys 2", true, ahu2Zones);

            BuildPlantSheet(root.transform, "Sheet_Chiller_Plant",
                new Vector3(roof.center.x, boardY, roof.center.z + span * 0.85f),
                roofStand,
                "CHILLER / TOWER  ·  plant I/O");

            // Small floor marker where a person would stand to read the sheets
            var stand = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            stand.name = "RoofReadVantage";
            stand.transform.SetParent(root.transform, false);
            stand.transform.position = new Vector3(roofStand.x, roof.max.y + 0.05f, roofStand.z);
            stand.transform.localScale = new Vector3(2.2f, 0.05f, 2.2f);
            var sm = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            var sc = new Color(0.2f, 0.55f, 0.75f, 1f);
            sm.color = sc;
            if (sm.HasProperty("_BaseColor")) sm.SetColor("_BaseColor", sc);
            stand.GetComponent<MeshRenderer>().sharedMaterial = sm;
            Object.DestroyImmediate(stand.GetComponent<Collider>());

            Debug.Log($"SensorBadgeFactory: Excel roof sheets AHU1={ahu1Zones.Count} AHU2={ahu2Zones.Count} + plant @ y={boardY:0.0}");
            return root;
        }

        static void BuildAhuSheet(
            Transform parent,
            string name,
            Vector3 worldPos,
            Vector3 lookAt,
            string sheetTitle,
            string airLoop,
            bool ahu2,
            List<TwinEntity> zones)
        {
            int ioRows = 7; // mean + OA Mix RA SA fan OA%
            int rows = 1 + zones.Count + 1 + ioRows; // title spacer counted in panel height
            var sheet = MakeSheetPanel(parent, name, worldPos, lookAt, sheetTitle, rows);

            int r = 0;
            AddHeaderRow(sheet, r++, "POINT", "READING");
            foreach (var z in zones)
            {
                AddRow(sheet, r++, SensorBadgeKind.ZoneTemp, z.entityId, airLoop, ahu2);
            }
            AddSectionRow(sheet, r++, "— AHU I/O —");
            AddRow(sheet, r++, SensorBadgeKind.AhuZoneMean, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuOa, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuMix, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuReturn, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuLeave, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuFanPlr, null, airLoop, ahu2);
            AddRow(sheet, r++, SensorBadgeKind.AhuOaFrac, null, airLoop, ahu2);
        }

        static void BuildPlantSheet(
            Transform parent,
            string name,
            Vector3 worldPos,
            Vector3 lookAt,
            string sheetTitle)
        {
            int rows = 1 + 12;
            var sheet = MakeSheetPanel(parent, name, worldPos, lookAt, sheetTitle, rows);
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
            Transform parent,
            string name,
            Vector3 worldPos,
            Vector3 lookAt,
            string sheetTitle,
            int dataRows)
        {
            var sheet = new GameObject(name);
            sheet.transform.SetParent(parent, false);
            sheet.transform.position = worldPos;

            // Face the rooftop vantage; +180° so TextMesh (+Z) is readable (not mirrored)
            Vector3 flat = lookAt - worldPos;
            flat.y = 0f;
            if (flat.sqrMagnitude < 0.01f) flat = Vector3.forward;
            sheet.transform.rotation =
                Quaternion.LookRotation(flat.normalized, Vector3.up) * Quaternion.Euler(0f, 180f, 0f);

            // Grab handle at the sheet pivot (move THIS object — all rows follow)
            var handle = GameObject.CreatePrimitive(PrimitiveType.Cube);
            handle.name = "SheetGrabHandle";
            handle.transform.SetParent(sheet.transform, false);
            handle.transform.localPosition = Vector3.zero;
            handle.transform.localScale = new Vector3(0.45f, 0.45f, 0.45f);
            var hm = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            var hc = new Color(0.25f, 0.75f, 0.95f, 1f);
            hm.color = hc;
            if (hm.HasProperty("_BaseColor")) hm.SetColor("_BaseColor", hc);
            handle.GetComponent<MeshRenderer>().sharedMaterial = hm;

            // Title + rows anchored at pivot so they are not floating meters away
            var titleGo = new GameObject("SheetTitle");
            titleGo.transform.SetParent(sheet.transform, false);
            titleGo.transform.localPosition = new Vector3(0f, 0.6f, 0f);
            titleGo.transform.localRotation = Quaternion.identity;
            var tm = titleGo.AddComponent<TextMesh>();
            tm.text = sheetTitle;
            tm.characterSize = 0.22f;
            tm.fontSize = 68;
            tm.anchor = TextAnchor.MiddleLeft;
            tm.alignment = TextAlignment.Left;
            tm.color = new Color(0.92f, 0.98f, 0.95f);

            var content = new GameObject("Rows");
            content.transform.SetParent(sheet.transform, false);
            content.transform.localPosition = new Vector3(0f, -0.6f, 0f);
            content.transform.localRotation = Quaternion.identity;
            return content.transform;
        }

        static void AddHeaderRow(Transform rowsRoot, int row, string a, string b)
        {
            var go = new GameObject($"Header_{row}");
            go.transform.SetParent(rowsRoot, false);
            go.transform.localPosition = new Vector3(0f, -row * RowPitch, 0f);

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
            MakeCellText(go.transform, "Section", new Vector3(ColPoint, 0f, 0f), text,
                new Color(0.85f, 0.78f, 0.45f), true);
        }

        static void AddRow(
            Transform rowsRoot,
            int row,
            SensorBadgeKind kind,
            string zoneId,
            string airLoop,
            bool ahu2)
        {
            var go = new GameObject($"Row_{row}_{kind}");
            go.transform.SetParent(rowsRoot, false);
            go.transform.localPosition = new Vector3(0f, -row * RowPitch, 0f);

            var titleGo = new GameObject("Title");
            titleGo.transform.SetParent(go.transform, false);
            var titleTm = titleGo.AddComponent<TextMesh>();

            var valueGo = new GameObject("Value");
            valueGo.transform.SetParent(go.transform, false);
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
            badge.titleValueGap = 0.5f;
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
            var tm = go.AddComponent<TextMesh>();
            tm.text = text;
            tm.characterSize = boldish ? 0.15f : 0.14f;
            tm.fontSize = boldish ? 52 : 48;
            tm.anchor = TextAnchor.MiddleLeft;
            tm.alignment = TextAlignment.Left;
            tm.color = col;
            return tm;
        }

        static Bounds ComputeRoofBounds()
        {
            var bounds = new Bounds(Vector3.zero, Vector3.one);
            bool any = false;
            foreach (var te in Object.FindObjectsByType<TwinEntity>())
            {
                if (te.entityType != "zone") continue;
                if (te.displayName == null || !te.displayName.Contains("Floor_6")) continue;
                foreach (var r in te.GetComponentsInChildren<Renderer>())
                {
                    if (!any) { bounds = r.bounds; any = true; }
                    else bounds.Encapsulate(r.bounds);
                }
            }
            if (!any)
            {
                var massing = GameObject.Find("Liberty100Massing");
                if (massing != null)
                {
                    foreach (var r in massing.GetComponentsInChildren<Renderer>())
                    {
                        if (!any) { bounds = r.bounds; any = true; }
                        else bounds.Encapsulate(r.bounds);
                    }
                }
            }
            if (!any)
                bounds = new Bounds(new Vector3(20f, 24f, -20f), new Vector3(40f, 2f, 30f));
            return bounds;
        }
    }
}
