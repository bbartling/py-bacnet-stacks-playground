using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>DEMO Main Chiller + CoolingTower on roof; airplane props on tower.</summary>
    public static class XrayPlantFactory
    {
        public static GameObject Build(Transform parent, Vector3 chillerPos, Vector3 towerPos)
        {
            var old = GameObject.Find("TwinXrayPlant");
            if (old != null)
            {
                if (Application.isPlaying) Object.Destroy(old);
                else Object.DestroyImmediate(old);
            }

            var root = new GameObject("TwinXrayPlant");
            if (parent != null) root.transform.SetParent(parent, false);

            var frameMat = Mat(new Color(0.35f, 0.38f, 0.42f));
            var chwMat = Mat(new Color(0.25f, 0.55f, 0.95f));
            var cwMat = Mat(new Color(0.15f, 0.65f, 0.70f));
            var fanMat = Mat(new Color(0.18f, 0.18f, 0.20f));

            var chiller = new GameObject("MainChiller");
            chiller.transform.SetParent(root.transform, false);
            chiller.transform.position = chillerPos;

            Prim(PrimitiveType.Cube, "Pad", chiller.transform, Vector3.zero, new Vector3(5.5f, 0.25f, 3.2f), frameMat);
            var barrel = Prim(PrimitiveType.Cylinder, "Barrel", chiller.transform, new Vector3(0, 1.4f, 0), new Vector3(2.2f, 1.2f, 2.2f), frameMat);
            barrel.transform.localRotation = Quaternion.Euler(0f, 0f, 90f);
            Prim(PrimitiveType.Cube, "Compressor", chiller.transform, new Vector3(1.8f, 1.2f, 0), new Vector3(1.4f, 1.6f, 1.6f), Mat(new Color(0.28f, 0.3f, 0.34f)));
            Prim(PrimitiveType.Cube, "CHW_Header", chiller.transform, new Vector3(-2.2f, 1.0f, 0), new Vector3(0.9f, 0.7f, 1.4f), chwMat);
            Prim(PrimitiveType.Cube, "CW_Header", chiller.transform, new Vector3(0, 2.5f, 0), new Vector3(1.2f, 0.5f, 1.0f), cwMat);

            OrthoMepRouter.MakePort(chiller.transform, "Port_CHW_Header", new Vector3(-2.7f, 1.0f, 0f), -Vector3.right);
            OrthoMepRouter.MakePort(chiller.transform, "Port_CHW_Return", new Vector3(-2.7f, 1.0f, 0.7f), -Vector3.right);
            OrthoMepRouter.MakePort(chiller.transform, "Port_CW_Out", new Vector3(0f, 2.5f, 0.6f), Vector3.forward);
            OrthoMepRouter.MakePort(chiller.transform, "Port_CW_Return", new Vector3(0.8f, 2.5f, 0f), Vector3.right);

            var impellerPivot = AirplanePropFactory.BuildFacingX(
                chiller.transform, "ChillerImpellerPivot", new Vector3(1.8f, 1.2f, 0), 0.55f, fanMat, 3);

            var cte = chiller.AddComponent<TwinEntity>();
            cte.entityId = "chiller_main";
            cte.entityType = "chiller_proxy";
            cte.displayName = "Main Chiller (DEMO)";
            cte.isDemoProxy = true;

            var labelGo = new GameObject("Label");
            labelGo.transform.SetParent(chiller.transform, false);
            labelGo.transform.localPosition = new Vector3(0, 3.2f, 0);
            var tm = labelGo.AddComponent<TextMesh>();
            tm.text = "Main Chiller";
            tm.characterSize = 0.18f;
            tm.fontSize = 48;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = new Color(0.7f, 0.85f, 1f);

            var tower = new GameObject("CoolingTower");
            tower.transform.SetParent(root.transform, false);
            tower.transform.position = towerPos;

            Prim(PrimitiveType.Cube, "Basin", tower.transform, new Vector3(0, 0.4f, 0), new Vector3(4.5f, 0.8f, 4.5f), cwMat);
            Prim(PrimitiveType.Cube, "Fill", tower.transform, new Vector3(0, 2.2f, 0), new Vector3(4.0f, 2.8f, 4.0f), TransMat(new Color(0.4f, 0.55f, 0.6f, 0.35f)));
            Prim(PrimitiveType.Cube, "FanDeck", tower.transform, new Vector3(0, 4.0f, 0), new Vector3(4.2f, 0.25f, 4.2f), frameMat);

            OrthoMepRouter.MakePort(tower.transform, "Port_CW_In", new Vector3(0f, 0.8f, -2.4f), -Vector3.forward);
            OrthoMepRouter.MakePort(tower.transform, "Port_CW_Out", new Vector3(2.4f, 0.8f, 0f), Vector3.right);
            OrthoMepRouter.MakePort(tower.transform, "Port_Basin", new Vector3(0f, 0.9f, 0f), Vector3.up);

            var towerPivot = AirplanePropFactory.BuildFacingUp(
                tower.transform, "TowerFanPivot", new Vector3(0, 4.55f, 0), 1.6f, fanMat, 3);

            var tte = tower.AddComponent<TwinEntity>();
            tte.entityId = "cooling_tower_main";
            tte.entityType = "tower_proxy";
            tte.displayName = "Cooling Tower (DEMO)";
            tte.isDemoProxy = true;

            var tlabel = new GameObject("Label");
            tlabel.transform.SetParent(tower.transform, false);
            tlabel.transform.localPosition = new Vector3(0, 5.8f, 0);
            var ttm = tlabel.AddComponent<TextMesh>();
            ttm.text = "Cooling Tower";
            ttm.characterSize = 0.16f;
            ttm.fontSize = 44;
            ttm.anchor = TextAnchor.MiddleCenter;
            ttm.color = new Color(0.5f, 0.9f, 0.85f);

            var plant = root.AddComponent<PlantVisualController>();
            plant.chillerRoot = chiller.transform;
            plant.towerRoot = tower.transform;
            plant.chillerSpin = impellerPivot;
            plant.towerSpin = towerPivot;

            return root;
        }

        static GameObject Prim(PrimitiveType type, string name, Transform parent, Vector3 localPos, Vector3 scale, Material mat)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = scale;
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
            return go;
        }

        static Material Mat(Color c)
        {
            var m = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            m.color = c;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            return m;
        }

        static Material TransMat(Color c)
        {
            var m = Mat(c);
            if (m.HasProperty("_Surface")) m.SetFloat("_Surface", 1f);
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.renderQueue = 3000;
            m.color = c;
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            return m;
        }
    }
}
