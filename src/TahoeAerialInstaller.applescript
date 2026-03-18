on run
  set installerPath to POSIX path of ((path to me as text) & "Contents:Resources:install-from-bundle.sh")

  display dialog "Install Tahoe Aerial Scheduler for this Mac user?\n\nThis will set up the menu bar app, runtime files, and launch agents in your home folder." buttons {"Cancel", "Install"} default button "Install" with title "Tahoe Aerial Scheduler"

  try
    do shell script quoted form of installerPath
    display dialog "Tahoe Aerial Scheduler is installed.\n\nThe menu bar app should appear in a moment." buttons {"OK"} default button "OK" with title "Tahoe Aerial Scheduler"
  on error errMsg number errNum
    display dialog "Install failed.\n\n" & errMsg buttons {"OK"} default button "OK" with icon stop with title "Tahoe Aerial Scheduler"
  end try
end run

