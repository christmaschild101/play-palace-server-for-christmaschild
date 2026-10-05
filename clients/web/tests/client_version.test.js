// Tests for the web client's own version data.
//
// Run with: node --test clients/web/tests/
//
// The version used to be written down in three places - two authorize packets
// and the page heading - and drifted apart. client-version.js is now the single
// source, and these tests keep it honest.

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  PLAYPALACE_VERSION,
  PLAYPALACE_VERSION_MAJOR,
  PLAYPALACE_VERSION_MINOR,
  PLAYPALACE_VERSION_PATCH,
  versionDict,
} from "../client-version.js";

const appSource = readFileSync(new URL("../app.js", import.meta.url), "utf8");

test("the client reports twelve", () => {
  assert.equal(PLAYPALACE_VERSION, "12.0.0");
});

test("the numeric parts agree with the string", () => {
  assert.equal(PLAYPALACE_VERSION_MAJOR, 12);
  assert.equal(PLAYPALACE_VERSION_MINOR, 0);
  assert.equal(PLAYPALACE_VERSION_PATCH, 0);
});

test("versionDict is what the authorize packet sends", () => {
  assert.deepEqual(versionDict(), { major: 12, minor: 0, patch: 0 });
});

test("no version triple is hardcoded in app.js", () => {
  assert.ok(
    !/major:\s*\d+/.test(appSource),
    "app.js should take the version from client-version.js, not a literal",
  );
});

test("both authorize packets use the shared version", () => {
  const uses = appSource.match(/\.\.\.versionDict\(\)/g) || [];
  assert.equal(uses.length, 2, "expected both authorize payloads to use versionDict()");
});

test("the heading is filled in from the version module", () => {
  assert.ok(
    appSource.includes("PLAYPALACE_VERSION"),
    "app.js should render the heading from PLAYPALACE_VERSION",
  );
});