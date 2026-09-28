using System;

/// <summary>
/// Command-line facts read once at process start: whether a trainer launched this player (the
/// --mlagents-port argument ML-Agents' own Academy also reads, Runtime/Academy.cs:ReadPortFromArgs) and
/// which scene, if any, was requested with --scene. Fixed for the life of the process, so anything gated
/// on these values (the scene menu button, the recording button) never flickers once decided.
/// </summary>
public static class LaunchOptions
{
    const string ArgTrainerPort = "--mlagents-port";
    const string ArgScene = "--scene";

    public static bool StartedByTrainer { get; }
    public static string RequestedScene { get; }

    static LaunchOptions()
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length; i++)
        {
            if (string.Equals(args[i], ArgTrainerPort, StringComparison.OrdinalIgnoreCase))
                StartedByTrainer = true;
            else if (string.Equals(args[i], ArgScene, StringComparison.OrdinalIgnoreCase) && i + 1 < args.Length)
                RequestedScene = args[i + 1];
        }
    }
}
