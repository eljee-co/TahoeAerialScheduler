on run
  set installerPath to POSIX path of ((path to me as text) & "Contents:Resources:install-from-bundle.sh")
  set schedulerRunnerPath to POSIX path of (path to home folder) & "Library/Application Support/TahoeAerialScheduler/run-scheduler.sh"

  display dialog "Install Tahoe Aerial Scheduler for this Mac user?\n\nThis will set up the menu bar app, runtime files, and launch agents in your home folder." buttons {"Cancel", "Install"} default button "Install" with title "Tahoe Aerial Scheduler"

  try
    do shell script quoted form of installerPath
    set missingAssetsMessage to do shell script quoted form of schedulerRunnerPath & " missing-assets"

    if missingAssetsMessage is not "" then
      set dialogResult to display dialog "Tahoe Aerial Scheduler is installed, but some Tahoe clips still need to be downloaded.\n\n" & missingAssetsMessage buttons {"Later", "Open Wallpaper Settings"} default button "Open Wallpaper Settings" with title "Tahoe Downloads Needed"
      if button returned of dialogResult is "Open Wallpaper Settings" then
        do shell script quoted form of schedulerRunnerPath & " open-wallpaper-settings"
      end if
    else
      display dialog "Tahoe Aerial Scheduler is installed.\n\nThe menu bar app should appear in a moment." buttons {"OK"} default button "OK" with title "Tahoe Aerial Scheduler"
    end if
  on error errMsg number errNum
    display dialog "Install failed.\n\n" & errMsg buttons {"OK"} default button "OK" with icon stop with title "Tahoe Aerial Scheduler"
  end try
end run
