const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const menu = vm.createContext({
  Application: { currentApplication: () => ({}) },
  ObjC: { import() {}, unwrap: (value) => value, registerSubclass() {} },
  $: { NSHomeDirectory: () => "/tmp/tahoe-menu-test" },
});
vm.runInContext(fs.readFileSync(path.join(__dirname, "../src/TahoeAerialMenu.js"), "utf8"), menu);

test("the menu names the observed clip when it differs from the schedule", () => {
  const info = { current_slot: { label: "Tahoe Day" }, playback: { status: "mismatch", label: "Golden Gate Day" } };
  assert.equal(menu.playbackTitle(info), "Playing: Golden Gate Day");
  assert.equal(menu.playbackWarning(info), "Background needs recovery");
});

test("unavailable playback does not claim the scheduled clip is playing", () => {
  const info = { current_slot: { label: "Tahoe Day" }, playback: { status: "unverified", label: null } };
  assert.equal(menu.playbackTitle(info), "Playback not yet verified");
  assert.equal(menu.playbackWarning(info), "Playback not yet verified");
});

test("verified playback has no warning", () => {
  const info = { playback: { status: "verified", label: "Tahoe Morning" } };
  assert.equal(menu.playbackTitle(info), "Playing: Morning");
  assert.equal(menu.playbackWarning(info), null);
});

test("missing downloads have a specific warning", () => {
  assert.equal(menu.playbackWarning({ playback: { status: "missing_download" } }), "Scheduled clip needs downloading");
});
