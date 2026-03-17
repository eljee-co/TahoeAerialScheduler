ObjC.import("AppKit");
ObjC.import("Foundation");
ObjC.import("stdlib");

const app = Application.currentApplication();
app.includeStandardAdditions = true;

const homeDir = ObjC.unwrap($.NSHomeDirectory());
const schedulerDir = `${homeDir}/Library/Application Support/TahoeAerialScheduler`;
const schedulerRunnerPath = `${schedulerDir}/run-scheduler.sh`;
const configPath = `${schedulerDir}/config.json`;
const menuLogPath = `${schedulerDir}/menu-ui.log`;

const assetOrder = ["tahoe_morning", "tahoe_day", "tahoe_evening", "tahoe_night"];

let delegate = null;
let statusItem = null;
let refreshTimer = null;

function logMessage(message) {
  const timestamp = (new Date()).toISOString();
  app.doShellScript(
    `/bin/echo ${shellQuote(`[${timestamp}] ${message}`)} >> ${shellQuote(menuLogPath)}`
  );
}

function shellQuote(value) {
  return "'" + String(value).replace(/'/g, "'\\''") + "'";
}

function runScheduler(args) {
  const command = [shellQuote(schedulerRunnerPath)]
    .concat(args.map(shellQuote))
    .join(" ");
  return app.doShellScript(command);
}

function loadInfo() {
  return JSON.parse(runScheduler(["info-json"]));
}

function showNotification(message) {
  app.displayNotification(message, { withTitle: "Tahoe Aerial" });
}

function promptForText(prompt, defaultAnswer) {
  $.NSApp.activateIgnoringOtherApps(true);
  const result = app.displayDialog(prompt, {
    defaultAnswer,
    buttons: ["Cancel", "Save"],
    defaultButton: "Save",
  });
  return result.textReturned;
}

function openTextEdit(path) {
  app.doShellScript(`/usr/bin/open -a TextEdit ${shellQuote(path)}`);
}

function assetLabel(info, assetKey) {
  return info.assets[assetKey].label;
}

function shortAssetLabel(info, assetKey) {
  return assetLabel(info, assetKey).replace(/^Tahoe\s+/, "");
}

function nextScheduleEntry(info, start) {
  const entries = info.schedule;
  for (let index = 0; index < entries.length; index += 1) {
    if (entries[index].start === start) {
      return entries[(index + 1) % entries.length];
    }
  }
  return entries[0];
}

function slotSummaryTitle(info, start) {
  const nextEntry = nextScheduleEntry(info, start);
  return `${start}-${nextEntry.start}`;
}

function nsString(value) {
  return $.NSString.stringWithString(String(value));
}

function menuSymbolName(period) {
  switch (period) {
    case "night":
      return "moon.stars.fill";
    case "morning":
      return "sunrise.fill";
    case "day":
      return "sun.max.fill";
    case "evening":
      return "sunset.fill";
    default:
      return "mountain.2.fill";
  }
}

function menuImageFor(period) {
  const image = $.NSImage.imageWithSystemSymbolNameAccessibilityDescription(
    nsString(menuSymbolName(period)),
    nsString("Tahoe Aerial")
  );
  if (image) {
    image.setTemplate(true);
  }
  return image;
}

function separator() {
  return $.NSMenuItem.separatorItem;
}

function standardMenuItem(title, actionName, target, enabled = true) {
  const item = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(
    nsString(title),
    actionName ? actionName : null,
    nsString("")
  );
  if (actionName) {
    item.setTarget(target);
  }
  item.setEnabled(enabled);
  return item;
}

function representedItem(title, actionName, representedValue, target, enabled = true) {
  const item = standardMenuItem(title, actionName, target, enabled);
  item.setRepresentedObject(nsString(representedValue));
  return item;
}

function refreshMenu() {
  try {
    const info = loadInfo();
    const currentLabel = info.current_slot.label;
    const nextSlotStart = info.next_slot.start;

    if (!statusItem) {
      statusItem = $.NSStatusBar.systemStatusBar.statusItemWithLength($.NSVariableStatusItemLength);
    }

    statusItem.button.setImage(menuImageFor(info.current_slot.period));
    statusItem.button.setTitle(nsString(""));
    statusItem.button.setToolTip(
      nsString(`${currentLabel} now, next change at ${nextSlotStart}`)
    );

    const menu = $.NSMenu.alloc.initWithTitle(nsString("Tahoe Aerial"));
    menu.setAutoenablesItems(false);

    menu.addItem(
      standardMenuItem(`Now: ${shortAssetLabel(info, info.current_slot.asset_key)}`, null, null, false)
    );
    menu.addItem(separator());

    info.schedule.forEach((entry) => {
      const start = entry.start;
      const submenuItem = standardMenuItem(slotSummaryTitle(info, start), null, null, true);
      const submenu = $.NSMenu.alloc.initWithTitle(nsString(`${start} block`));
      submenu.setAutoenablesItems(false);

      submenu.addItem(
        standardMenuItem(`Current clip: ${assetLabel(info, entry.asset_key)}`, null, null, false)
      );
      submenu.addItem(
        representedItem("Change start time...", "changeStartTime:", start, delegate, true)
      );
      submenu.addItem(separator());

      assetOrder.forEach((assetKey) => {
        const title = assetLabel(info, assetKey);
        const value = JSON.stringify({ start, assetKey });
        const item = representedItem(title, "setSlot:", value, delegate, true);

        if (entry.asset_key === assetKey) {
          item.setState($.NSControlStateValueOn);
        }

        submenu.addItem(item);
      });

      submenuItem.setSubmenu(submenu);
      menu.addItem(submenuItem);
    });

    menu.addItem(separator());
    menu.addItem(standardMenuItem("Open Config", "openConfig:", delegate, true));
    menu.addItem(separator());
    menu.addItem(standardMenuItem("Quit Tahoe Menu", "quitApp:", delegate, true));

    statusItem.setMenu(menu);
    logMessage(`refreshed menu for ${info.current_slot.asset_key}`);
  } catch (error) {
    if (!statusItem) {
      statusItem = $.NSStatusBar.systemStatusBar.statusItemWithLength($.NSVariableStatusItemLength);
    }

    const message = error.toString();
    statusItem.button.setImage(menuImageFor(null));
    statusItem.button.setTitle(nsString(""));
    statusItem.button.setToolTip(nsString(message));

    const menu = $.NSMenu.alloc.initWithTitle(nsString("Tahoe Aerial Error"));
    menu.setAutoenablesItems(false);
    menu.addItem(standardMenuItem("Tahoe menu hit an error", null, null, false));
    menu.addItem(standardMenuItem(message, null, null, false));
    menu.addItem(separator());
    menu.addItem(standardMenuItem("Open Config", "openConfig:", delegate, true));
    menu.addItem(standardMenuItem("Quit Tahoe Menu", "quitApp:", delegate, true));
    statusItem.setMenu(menu);
    logMessage(`menu error: ${message}`);
  }
}

ObjC.registerSubclass({
  name: "TahoeMenuDelegate",
  superclass: "NSObject",
  protocols: ["NSApplicationDelegate"],
  methods: {
    "refreshTimerFired:": {
      types: ["void", ["id"]],
      implementation: function () {
        refreshMenu();
      },
    },

    "setSlot:": {
      types: ["void", ["id"]],
      implementation: function (sender) {
        try {
          const raw = ObjC.unwrap(sender.representedObject);
          const payload = JSON.parse(raw);
          const info = loadInfo();
          const label = shortAssetLabel(info, payload.assetKey);
          runScheduler(["set-slot", payload.start, payload.assetKey]);
          runScheduler(["apply"]);
          refreshMenu();
          showNotification(`${payload.start} now uses ${label}`);
        } catch (error) {
          showNotification(`Update failed: ${error}`);
        }
      },
    },

    "changeStartTime:": {
      types: ["void", ["id"]],
      implementation: function (sender) {
        try {
          const oldStart = ObjC.unwrap(sender.representedObject);
          const newStart = promptForText(`New start time for the ${oldStart} block (HH:MM)`, oldStart);
          runScheduler(["set-start-time", oldStart, newStart]);
          runScheduler(["apply"]);
          refreshMenu();
          showNotification(`Moved the ${oldStart} block to ${newStart}`);
        } catch (error) {
          const message = String(error);
          if (message.indexOf("User canceled") >= 0) {
            return;
          }
          showNotification(`Time change failed: ${error}`);
        }
      },
    },

    "openConfig:": {
      types: ["void", ["id"]],
      implementation: function () {
        openTextEdit(configPath);
      },
    },

    "quitApp:": {
      types: ["void", ["id"]],
      implementation: function () {
        $.NSStatusBar.systemStatusBar.removeStatusItem(statusItem);
        $.NSApp.terminate(null);
      },
    },
  },
});

function run() {
  $.NSApplication.sharedApplication;
  $.NSApp.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
  delegate = $.TahoeMenuDelegate.alloc.init;
  $.NSApp.setDelegate(delegate);
  refreshMenu();
  refreshTimer = $.NSTimer.scheduledTimerWithTimeIntervalTargetSelectorUserInfoRepeats(
    60.0,
    delegate,
    "refreshTimerFired:",
    null,
    true
  );
  logMessage("menu app started");
  $.NSApp.run();
}

