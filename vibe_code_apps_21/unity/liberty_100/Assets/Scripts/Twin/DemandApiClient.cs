using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace Vibe21.Twin
{
    [Serializable]
    public class DemandPredictRequest
    {
        public int hour_ending = 15;
        public float oat_c = 32f;
        public float rh_pct = 55f;
        public float ghi = 700f;
        public float occupied = 1f;
        public int in_dr_window = 1;
        public float precool_f;
        public float relax_clg_f;
        public float relax_htg_f;
        public float dat_delta_f;
        public float chw_avail = 1f;
        public float fan_avail = 1f;
        public float deadband_target_f;
        public string strategy_id = "baseline";
        public string phase = "baseline";
        public string dow = "Wednesday";
        public float facility_kw_lag1 = 200f;
        public float facility_kw_lag2 = 195f;
        public float oat_lag1 = 31f;
    }

    [Serializable]
    public class DemandPredictResponse
    {
        public float facility_kw;
        public TwinIoPayload twin_io;
        public string unit;
        public string model_id;
        public string model_status;
        public string strategy_id;
        public string phase;
        public int hour_ending;
        public Provenance provenance;
    }

    [Serializable]
    public class Provenance
    {
        public string source;
        public string engine;
        public string artifact_sha256;
        public string honesty;
    }

    [Serializable]
    class HealthPayload
    {
        public string status;
        public string model_id;
        public string model_status;
        public string model_error;
    }

    /// <summary>HTTP client for Flask demand_hourly inference (Editor :5050 or WebGL same-origin).</summary>
    public class DemandApiClient : MonoBehaviour
    {
        public enum HealthState { Offline, Online, Degraded }

        public string baseUrl = "http://127.0.0.1:5050";
        public DemandPredictResponse lastResponse;

        void Awake()
        {
            ResolveBaseUrl();
        }

        void ResolveBaseUrl()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            try
            {
                var abs = Application.absoluteURL;
                if (!string.IsNullOrEmpty(abs))
                {
                    var uri = new Uri(abs);
                    baseUrl = uri.GetLeftPart(UriPartial.Authority);
                }
            }
            catch
            {
                // keep inspector default
            }
#else
            if (string.IsNullOrWhiteSpace(baseUrl))
                baseUrl = "http://127.0.0.1:5050";
#endif
        }

        public IEnumerator Predict(DemandPredictRequest req, Action<DemandPredictResponse> onOk, Action<string> onErr)
        {
            var url = baseUrl.TrimEnd('/') + "/api/v1/predict/demand_hourly";
            var json = JsonUtility.ToJson(req);
            using var uwr = new UnityWebRequest(url, "POST");
            byte[] body = Encoding.UTF8.GetBytes(json);
            uwr.uploadHandler = new UploadHandlerRaw(body);
            uwr.downloadHandler = new DownloadHandlerBuffer();
            uwr.SetRequestHeader("Content-Type", "application/json");
            yield return uwr.SendWebRequest();
            if (uwr.result != UnityWebRequest.Result.Success)
            {
                onErr?.Invoke(uwr.error + " " + uwr.downloadHandler.text);
                yield break;
            }
            var text = uwr.downloadHandler.text;
            text = System.Text.RegularExpressions.Regex.Replace(
                text, ",\\s*\"feature_cols\"\\s*:\\s*\\[[^\\]]*\\]", "");
            var resp = JsonUtility.FromJson<DemandPredictResponse>(text);
            lastResponse = resp;
            onOk?.Invoke(resp);
        }

        public IEnumerator Health(Action<bool, string> done)
        {
            yield return HealthDetailed((state, detail) => done?.Invoke(state == HealthState.Online, detail));
        }

        public IEnumerator HealthDetailed(Action<HealthState, string> done)
        {
            var url = baseUrl.TrimEnd('/') + "/api/v1/health";
            using var uwr = UnityWebRequest.Get(url);
            yield return uwr.SendWebRequest();
            if (uwr.result != UnityWebRequest.Result.Success)
            {
                done?.Invoke(HealthState.Offline, "Machine learning web app service unreachable");
                yield break;
            }
            var text = uwr.downloadHandler?.text ?? "";
            HealthPayload payload = null;
            try { payload = JsonUtility.FromJson<HealthPayload>(text); }
            catch { /* ignore */ }

            int code = (int)uwr.responseCode;
            string status = payload?.status ?? "";
            if (code == 503 || string.Equals(status, "degraded", StringComparison.OrdinalIgnoreCase))
            {
                string err = !string.IsNullOrEmpty(payload?.model_error)
                    ? payload.model_error
                    : "Model missing or degraded";
                done?.Invoke(HealthState.Degraded, err);
                yield break;
            }
            string okDetail = !string.IsNullOrEmpty(payload?.model_id)
                ? $"{payload.model_id} [{payload.model_status}]"
                : "OK";
            done?.Invoke(HealthState.Online, okDetail);
        }
    }
}
