// OctopathWorldOverhaul.exe - starts the mod's Python code with the bundled Python runtime.
//
// The release ships the official python.org runtime (runtime\) and the mod's source (app\)
// as plain files. This exe only runs  runtime\pythonw.exe app\launch_octopath.py <args>,
// passing its own command line through unchanged (Steam's --wrap %command% included), and
// waits so Steam sees the game running for as long as the launcher does.
// Build: csc /target:winexe /out:OctopathWorldOverhaul.exe OctopathWorldOverhaul.cs
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Launcher
{
    const string Title = "Orsterra Unbound";

    // everything after the program name, exactly as Windows received it
    static string Arguments()
    {
        string cmd = Environment.CommandLine;
        int i = 0;
        if (cmd.StartsWith("\""))
        {
            int close = cmd.IndexOf('"', 1);
            i = close < 0 ? cmd.Length : close + 1;
        }
        else
        {
            while (i < cmd.Length && cmd[i] != ' ' && cmd[i] != '\t') i++;
        }
        return cmd.Substring(i).TrimStart();
    }

    [STAThread]
    static int Main()
    {
        string exe = Process.GetCurrentProcess().MainModule.FileName;
        string dir = Path.GetDirectoryName(exe);
        string python = Path.Combine(dir, "runtime", "pythonw.exe");
        string script = Path.Combine(dir, "app", "launch_octopath.py");

        if (!File.Exists(python) || !File.Exists(script))
        {
            string where = dir.IndexOf("\\Temp\\", StringComparison.OrdinalIgnoreCase) >= 0
                ? "\n\nIt looks like it was opened straight from the zip. Right-click the zip, "
                  + "choose \"Extract All...\", then run OctopathWorldOverhaul.exe from the "
                  + "extracted folder."
                : "\n\nExtract the whole zip again, keeping all the files and folders together.";
            MessageBox.Show("Some of Orsterra Unbound's files are missing (the runtime or app "
                            + "folder)." + where, Title, MessageBoxButtons.OK,
                            MessageBoxIcon.Warning);
            return 1;
        }

        var info = new ProcessStartInfo(python, "\"" + script + "\" " + Arguments());
        info.UseShellExecute = false;
        info.WorkingDirectory = dir;
        info.EnvironmentVariables["ORSTERRA_LAUNCHER"] = exe;
        try
        {
            using (Process p = Process.Start(info))
            {
                p.WaitForExit();
                return p.ExitCode;
            }
        }
        catch (Exception e)
        {
            MessageBox.Show("Could not start Orsterra Unbound:\n\n" + e.Message, Title,
                            MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
