using System.Collections.Generic;
using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>
    /// Runtime particle flow cues for ducts, pipes, and cooling-tower drip/mist.
    /// Air and liquid rates are independent (fans vs pumps/chiller/tower).
    /// </summary>
    public class MepFlowFx : MonoBehaviour
    {
        public float airRate = 22f;
        public float liquidRate = 14f;
        public float dripRate = 40f;
        public float mistRate = 22f;
        public float minSegLen = 0.35f;
        [Range(0f, 1.5f)] public float flowLoad = 1f;
        public bool plantRunning = true;
        [Range(0f, 1.5f)] public float airLoad = 1f;
        public bool airRunning = true;
        [Range(0f, 1.5f)] public float liquidLoad = 1f;
        public bool liquidRunning = true;

        readonly List<ParticleSystem> _air = new List<ParticleSystem>();
        readonly List<ParticleSystem> _liquid = new List<ParticleSystem>();
        readonly List<ParticleSystem> _tower = new List<ParticleSystem>();

        public static MepFlowFx EnsureOn(GameObject root)
        {
            var fx = root.GetComponent<MepFlowFx>() ?? root.AddComponent<MepFlowFx>();
            return fx;
        }

        public void Clear()
        {
            _air.Clear();
            _liquid.Clear();
            _tower.Clear();
        }

        public void AddAlongPath(IList<Vector3[]> segs, Color color, bool air, float speed, float ductWidth)
        {
            if (segs == null) return;
            float rate = air ? airRate : liquidRate;
            foreach (var seg in segs)
            {
                if (seg == null || seg.Length < 2) continue;
                float len = Vector3.Distance(seg[0], seg[1]);
                if (len < minSegLen) continue;
                var ps = MakeStreak(seg[0], seg[1], color, rate, speed, air, ductWidth);
                if (ps == null) continue;
                if (air) _air.Add(ps);
                else _liquid.Add(ps);
            }
        }

        public void AddTowerFx(Transform towerRoot)
        {
            if (towerRoot == null) return;
            var white = new Color(0.95f, 0.97f, 1f, 0.75f);
            var basin = towerRoot.Find("Port_Basin");
            Vector3 dripAt = basin != null ? basin.position : towerRoot.position + Vector3.up * 0.9f;
            _tower.Add(MakeDrip(dripAt, white));

            Vector3 mistAt = towerRoot.position + Vector3.up * 4.6f;
            _tower.Add(MakeMist(mistAt, new Color(0.95f, 0.97f, 1f, 0.4f)));
        }

        /// <summary>Legacy: sets both air and liquid (prefer SetAirFlow / SetLiquidFlow).</summary>
        public void SetRunning(bool running, float load)
        {
            plantRunning = running;
            flowLoad = Mathf.Clamp(load, 0f, 1.5f);
            SetLiquidFlow(running, load);
        }

        public void SetAirFlow(bool running, float load)
        {
            airRunning = running;
            airLoad = Mathf.Clamp(load, 0f, 1.5f);
            ApplyRates();
        }

        public void SetLiquidFlow(bool running, float load)
        {
            liquidRunning = running;
            liquidLoad = Mathf.Clamp(load, 0f, 1.5f);
            plantRunning = running;
            flowLoad = liquidLoad;
            ApplyRates();
        }

        void Update()
        {
            bool paused = TwinMainMenu.Instance != null && TwinMainMenu.Instance.IsPaused;
            if (paused)
            {
                SetEmissionAll(0f);
                return;
            }
            ApplyRates();
        }

        void ApplyRates()
        {
            float airMul = airRunning ? airLoad : 0f;
            float liqMul = liquidRunning ? liquidLoad : 0f;
            foreach (var ps in _air)
                SetRate(ps, airRate * airMul);
            foreach (var ps in _liquid)
                SetRate(ps, liquidRate * liqMul);
            foreach (var ps in _tower)
                SetRate(ps, (ps.name.Contains("Mist") ? mistRate : dripRate) * liqMul);
        }

        void SetEmissionAll(float rate)
        {
            foreach (var ps in _air) SetRate(ps, rate);
            foreach (var ps in _liquid) SetRate(ps, rate);
            foreach (var ps in _tower) SetRate(ps, rate);
        }

        static void SetRate(ParticleSystem ps, float rate)
        {
            if (ps == null) return;
            var em = ps.emission;
            em.rateOverTime = rate;
            if (rate > 0.05f && !ps.isPlaying) ps.Play();
            if (rate <= 0.05f && ps.isPlaying) ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }

        ParticleSystem MakeStreak(Vector3 a, Vector3 b, Color color, float rate, float speed, bool air, float ductWidth)
        {
            Vector3 dir = b - a;
            float len = dir.magnitude;
            if (len < 0.05f) return null;
            speed = Mathf.Max(0.5f, speed);

            var go = new GameObject(air ? "FlowAir" : "FlowLiquid");
            go.transform.SetParent(transform, false);
            go.transform.position = a;
            go.transform.rotation = Quaternion.LookRotation(dir / len, Vector3.up);

            float cross = Mathf.Clamp(ductWidth * (air ? 0.28f : 0.32f), 0.05f, air ? 0.22f : 0.2f);
            float life = len / speed;

            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = life;
            main.startSpeed = speed;
            main.startSize = air ? 0.045f : 0.07f;
            main.startColor = color;
            main.maxParticles = air ? 60 : 100;
            main.simulationSpace = ParticleSystemSimulationSpace.Local;
            main.loop = true;
            main.playOnAwake = true;
            main.gravityModifier = 0f;

            var em = ps.emission;
            em.rateOverTime = air ? rate * 0.7f : rate;

            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(cross, air ? cross * 0.5f : cross, Mathf.Min(0.08f, len * 0.05f));
            shape.randomDirectionAmount = 0f;
            shape.sphericalDirectionAmount = 0f;

            var noise = ps.noise;
            noise.enabled = air;
            if (air)
            {
                noise.strength = 0.08f;
                noise.frequency = 0.4f;
            }

            var lim = ps.limitVelocityOverLifetime;
            lim.enabled = true;
            lim.limit = speed;
            lim.dampen = 1f;

            var col = ps.colorOverLifetime;
            col.enabled = true;
            var grad = new Gradient();
            if (air)
            {
                grad.SetKeys(
                    new[] { new GradientColorKey(color, 0f), new GradientColorKey(color, 1f) },
                    new[] { new GradientAlphaKey(0.15f, 0f), new GradientAlphaKey(0.55f, 0.35f), new GradientAlphaKey(0f, 1f) });
            }
            else
            {
                grad.SetKeys(
                    new[] { new GradientColorKey(color, 0f), new GradientColorKey(color, 1f) },
                    new[] { new GradientAlphaKey(0.75f, 0f), new GradientAlphaKey(0.85f, 0.5f), new GradientAlphaKey(0.2f, 1f) });
            }
            col.color = grad;

            var renderer = go.GetComponent<ParticleSystemRenderer>();
            if (air)
            {
                renderer.renderMode = ParticleSystemRenderMode.Stretch;
                renderer.lengthScale = 3.2f;
                renderer.velocityScale = 0.15f;
                renderer.cameraVelocityScale = 0f;
            }
            else
            {
                renderer.renderMode = ParticleSystemRenderMode.Billboard;
            }
            renderer.material = DefaultParticleMat(color);

            ps.Play();
            return ps;
        }

        ParticleSystem MakeDrip(Vector3 at, Color color)
        {
            var go = new GameObject("TowerDrip");
            go.transform.SetParent(transform, false);
            go.transform.position = at;

            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = 1.4f;
            main.startSpeed = 1.8f;
            main.startSize = 0.07f;
            main.startColor = color;
            main.gravityModifier = 0.85f;
            main.maxParticles = 120;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.loop = true;

            var em = ps.emission;
            em.rateOverTime = dripRate;

            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(2.2f, 0.1f, 2.2f);

            var renderer = go.GetComponent<ParticleSystemRenderer>();
            renderer.material = DefaultParticleMat(color);
            ps.Play();
            return ps;
        }

        ParticleSystem MakeMist(Vector3 at, Color color)
        {
            var go = new GameObject("TowerMist");
            go.transform.SetParent(transform, false);
            go.transform.position = at;

            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = 2.2f;
            main.startSpeed = 1.1f;
            main.startSize = 0.55f;
            main.startColor = color;
            main.maxParticles = 80;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.loop = true;

            var em = ps.emission;
            em.rateOverTime = mistRate;

            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 28f;
            shape.radius = 0.6f;

            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.y = new ParticleSystem.MinMaxCurve(1.4f);

            var col = ps.colorOverLifetime;
            col.enabled = true;
            var grad = new Gradient();
            grad.SetKeys(
                new[] { new GradientColorKey(color, 0f), new GradientColorKey(color, 1f) },
                new[] { new GradientAlphaKey(0.4f, 0f), new GradientAlphaKey(0f, 1f) });
            col.color = grad;

            var renderer = go.GetComponent<ParticleSystemRenderer>();
            renderer.material = DefaultParticleMat(color);
            ps.Play();
            return ps;
        }

        static Material DefaultParticleMat(Color c)
        {
            var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit")
                         ?? Shader.Find("Particles/Standard Unlit")
                         ?? Shader.Find("Sprites/Default")
                         ?? Shader.Find("Universal Render Pipeline/Unlit");
            var m = new Material(shader);
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            if (m.HasProperty("_Color")) m.SetColor("_Color", c);
            m.color = c;
            return m;
        }
    }
}
