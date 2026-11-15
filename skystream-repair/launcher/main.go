// SkyStream Windows repair launcher.
// Purpose: start the original unmodified Flutter executable with a bounded
// heap for its child Java/CloudStream engine. No persistent system changes.
// Windows build: go build -trimpath -ldflags="-H windowsgui" -o skystream.exe .
package main

import (
    "os"
    "os/exec"
    "path/filepath"
    "strings"
    "syscall"
)

func main() {
    self, err := os.Executable()
    if err != nil {
        return
    }
    dir := filepath.Dir(self)
    original := filepath.Join(dir, "skystream-core.exe")
    cmd := exec.Command(original, os.Args[1:]...)
    cmd.Dir = dir
    // Keep any existing JVM diagnostics switches, but override the max heap
    // for this child only. This is tailored to the user's 16 GB laptop.
    old := strings.TrimSpace(os.Getenv("JAVA_TOOL_OPTIONS"))
    options := strings.TrimSpace(old + " -Xmx6g")
    cmd.Env = append(os.Environ(), "JAVA_TOOL_OPTIONS="+options)
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
    _ = cmd.Start()
}
