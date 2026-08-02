using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>
/// Cannon-style WebGL → flask_app/webgl deploy copy for Vibe21 Liberty twin.
/// Batchmode: -executeMethod LibertyWebGLBuildPipeline.BuildFromCommandLine
/// </summary>
public static class LibertyWebGLBuildPipeline
{
    public const string TwinScenePath = "Assets/Scenes/Liberty100Twin.unity";
    public const string BuildOutputDirectory = "Builds/WebGL";
    public const string BuildManifestPath = "Builds/WebGL_BUILD_MANIFEST.json";

    /// <summary>Relative to vibe_code_apps_21/ (two levels above unity/liberty_100).</summary>
    public const string FlaskWebGLDirectory = "../../flask_app/webgl";
    public const string FlaskWebGLManifestPath = "../../flask_app/WEBGL_BUILD_MANIFEST.json";

    private static readonly string[] RequiredBuildPatterns =
    {
        "index.html",
        "Build/*.loader.js",
        "Build/*.framework.js",
        "Build/*.wasm",
        "Build/*.data"
    };

    [MenuItem("Vibe21/Configure WebGL For PA")]
    public static void ConfigureWebGL()
    {
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;
        PlayerSettings.WebGL.threadsSupport = false;
        PlayerSettings.WebGL.dataCaching = true;
        PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.ExplicitlyThrownExceptionsOnly;
        PlayerSettings.stripEngineCode = false;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.WebGL, true);
        // Match Editor (PC URP). Mobile quality + variant strip → invisible meshes in browser.
        QualitySettings.SetQualityLevel(1, true);

        EnsureTwinSceneInBuildSettings();
        AssetDatabase.SaveAssets();
        Debug.Log("Configured Liberty WebGL for PythonAnywhere (PC quality, compression off, no threads).");
    }

    [MenuItem("Vibe21/Build WebGL → flask_app/webgl")]
    public static void BuildWebGLAndDeploy()
    {
        ConfigureWebGL();

        string[] scenes = { TwinScenePath };
        if (!File.Exists(TwinScenePath))
            throw new FileNotFoundException("Twin scene missing", TwinScenePath);

        if (Directory.Exists(BuildOutputDirectory))
            Directory.Delete(BuildOutputDirectory, true);
        Directory.CreateDirectory(BuildOutputDirectory);

        BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = scenes,
            locationPathName = BuildOutputDirectory,
            target = BuildTarget.WebGL,
            options = BuildOptions.CleanBuildCache
        });

        if (report.summary.result != BuildResult.Succeeded)
            throw new InvalidOperationException("WebGL build failed: " + report.summary.result);

        ValidateRequiredBuildFiles(BuildOutputDirectory);
        WriteManifest(BuildOutputDirectory, BuildManifestPath, report.summary.totalWarnings);
        RefreshFlaskWebGLCopy();
        WriteManifest(FlaskWebGLDirectory, FlaskWebGLManifestPath, report.summary.totalWarnings);

        Debug.Log(
            $"Liberty WebGL OK. Output={Path.GetFullPath(BuildOutputDirectory)} " +
            $"Deploy={Path.GetFullPath(FlaskWebGLDirectory)} " +
            $"Size={report.summary.totalSize} Warnings={report.summary.totalWarnings}");
    }

    public static void BuildFromCommandLine()
    {
        BuildWebGLAndDeploy();
    }

    public static void EnsureTwinSceneInBuildSettings()
    {
        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene(TwinScenePath, true)
        };
    }

    public static void ValidateRequiredBuildFiles(string root)
    {
        foreach (string pattern in RequiredBuildPatterns)
        {
            string directory = Path.Combine(root, Path.GetDirectoryName(pattern) ?? string.Empty);
            string filePattern = Path.GetFileName(pattern);
            if (!Directory.Exists(directory) ||
                Directory.GetFiles(directory, filePattern, SearchOption.TopDirectoryOnly).Length == 0)
            {
                throw new FileNotFoundException($"Required WebGL build output is missing: {pattern}");
            }
        }
    }

    public static void RefreshFlaskWebGLCopy()
    {
        string dest = Path.GetFullPath(FlaskWebGLDirectory);
        if (Directory.Exists(dest))
            Directory.Delete(dest, true);
        CopyDirectory(Path.GetFullPath(BuildOutputDirectory), dest);
    }

    private static void CopyDirectory(string source, string destination)
    {
        Directory.CreateDirectory(destination);
        foreach (string directory in Directory.GetDirectories(source, "*", SearchOption.AllDirectories))
            Directory.CreateDirectory(directory.Replace(source, destination));

        foreach (string file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
        {
            string destinationFile = file.Replace(source, destination);
            Directory.CreateDirectory(Path.GetDirectoryName(destinationFile) ?? destination);
            File.Copy(file, destinationFile, true);
        }
    }

    private static void WriteManifest(string root, string outputPath, int warningCount)
    {
        string fullRoot = Path.GetFullPath(root);
        List<BuildFileEntry> files = Directory.GetFiles(fullRoot, "*", SearchOption.AllDirectories)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .Select(path => new BuildFileEntry
            {
                path = Path.GetRelativePath(fullRoot, path).Replace('\\', '/'),
                sizeBytes = new FileInfo(path).Length,
                sha256 = ComputeSha256(path)
            })
            .ToList();

        var manifest = new BuildManifest
        {
            generatedUtc = DateTime.UtcNow.ToString("O"),
            unityVersion = Application.unityVersion,
            warningCount = warningCount,
            fileCount = files.Count,
            totalSizeBytes = files.Sum(file => file.sizeBytes),
            files = files.ToArray()
        };

        string fullOut = Path.GetFullPath(outputPath);
        Directory.CreateDirectory(Path.GetDirectoryName(fullOut) ?? ".");
        File.WriteAllText(fullOut, JsonUtility.ToJson(manifest, true));
        Debug.Log($"Wrote manifest {fullOut} ({manifest.fileCount} files, {manifest.totalSizeBytes} bytes).");
    }

    private static string ComputeSha256(string path)
    {
        using SHA256 sha = SHA256.Create();
        using FileStream stream = File.OpenRead(path);
        return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", string.Empty);
    }

    [Serializable]
    private class BuildManifest
    {
        public string generatedUtc;
        public string unityVersion;
        public int warningCount;
        public int fileCount;
        public long totalSizeBytes;
        public BuildFileEntry[] files;
    }

    [Serializable]
    private class BuildFileEntry
    {
        public string path;
        public long sizeBytes;
        public string sha256;
    }
}
