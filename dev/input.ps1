# Synthetic mouse/keyboard input so Claude can drive the game window for testing.
#   input.ps1 -Click 1385,813
#   input.ps1 -Key RETURN -Repeat 2
#   input.ps1 -Key Z -DelayMs 300
param(
    [string]$Click,
    [string]$Key,
    [int]$Repeat = 1,
    [int]$DelayMs = 150,
    [string]$Hold,          # key to hold down (movement)
    [int]$HoldMs = 2000     # for how long
)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32In {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int n);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
    [DllImport("user32.dll")] public static extern short VkKeyScan(char ch);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint uCode, uint uMapType);
    public const uint LEFTDOWN = 0x0002, LEFTUP = 0x0004;
    public const uint KEYDOWN = 0x0000, KEYUP = 0x0002, SCANCODE = 0x0008;
    public static void ClickAt(int x, int y) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(80);
        mouse_event(LEFTDOWN, 0, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(50);
        mouse_event(LEFTUP, 0, 0, 0, IntPtr.Zero);
    }
    // Games usually read scan codes (DirectInput), so send both vk and scan.
    public static void Tap(byte vk) {
        byte scan = (byte)MapVirtualKey(vk, 0);
        keybd_event(vk, scan, KEYDOWN | SCANCODE, IntPtr.Zero);
        System.Threading.Thread.Sleep(60);
        keybd_event(vk, scan, KEYUP | SCANCODE, IntPtr.Zero);
    }
    // Hold a key down - needed to actually walk, which is how encounters are triggered.
    public static void Hold(byte vk, int ms) {
        byte scan = (byte)MapVirtualKey(vk, 0);
        keybd_event(vk, scan, KEYDOWN | SCANCODE, IntPtr.Zero);
        int waited = 0;
        while (waited < ms) {                 // re-assert so the game keeps seeing it held
            System.Threading.Thread.Sleep(40);
            keybd_event(vk, scan, KEYDOWN | SCANCODE, IntPtr.Zero);
            waited += 40;
        }
        keybd_event(vk, scan, KEYUP | SCANCODE, IntPtr.Zero);
    }
}
"@

$VK = @{
    'RETURN' = 0x0D; 'ESCAPE' = 0x1B; 'SPACE' = 0x20;
    'LEFT' = 0x25; 'UP' = 0x26; 'RIGHT' = 0x27; 'DOWN' = 0x28;
    'Z' = 0x5A; 'X' = 0x58; 'C' = 0x43; 'A' = 0x41; 'S' = 0x53; 'D' = 0x44;
    'E' = 0x45; 'Q' = 0x51; 'W' = 0x57; 'F' = 0x46; 'TAB' = 0x09;
}

# Bring the game to the front first - synthetic input goes to the focused window.
$game = Get-Process | Where-Object { $_.MainWindowTitle -eq 'OCTOPATH TRAVELER' } | Select-Object -First 1
if ($game) {
    [Win32In]::ShowWindow($game.MainWindowHandle, 9) | Out-Null   # SW_RESTORE
    [Win32In]::SetForegroundWindow($game.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 400
}

if ($Click) {
    $xy = $Click -split ','
    [Win32In]::ClickAt([int]$xy[0], [int]$xy[1])
    Write-Output "clicked $($xy[0]),$($xy[1])"
}
if ($Hold) {
    $h = $Hold.ToUpper()
    if (-not $VK.ContainsKey($h)) { Write-Error "unknown key $h"; exit 1 }
    [Win32In]::Hold([byte]$VK[$h], $HoldMs)
    Write-Output "held $h for ${HoldMs}ms"
}
if ($Key) {
    $k = $Key.ToUpper()
    if (-not $VK.ContainsKey($k)) { Write-Error "unknown key $k"; exit 1 }
    for ($i = 0; $i -lt $Repeat; $i++) {
        [Win32In]::Tap([byte]$VK[$k])
        Start-Sleep -Milliseconds $DelayMs
    }
    Write-Output "sent $k x$Repeat"
}
