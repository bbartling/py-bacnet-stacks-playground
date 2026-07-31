using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Global °C / °F display preference (temps only; kW stays kW).</summary>
    public static class TempUnits
    {
        public static bool UseFahrenheit { get; set; }

        public static float ToDisplay(float celsius) =>
            UseFahrenheit ? celsius * 9f / 5f + 32f : celsius;

        public static string Suffix => UseFahrenheit ? "°F" : "°C";

        public static string Format(float celsius, string decimals = "0.0") =>
            $"{ToDisplay(celsius).ToString(decimals)}{Suffix}";
    }
}
