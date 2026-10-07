// The web client's own version.
//
// This is the single source of truth for the browser client's version. It is
// deliberately *not* read from the server: an older server still reports its
// own number, and showing that made this client look out of date when it was
// not.
//
// Note this is separate from version.js, which is a cache-busting token loaded
// as a classic script by index.html and holds no version number.

export const PLAYPALACE_VERSION = "12.0";

// The version is written with as many parts as mean something, so "12.0" has
// only two; missing parts are zero. The packet always carries all three.
const PLAYPALACE_VERSION_PARTS = PLAYPALACE_VERSION.split(".").map(Number);

export const PLAYPALACE_VERSION_MAJOR = PLAYPALACE_VERSION_PARTS[0];
export const PLAYPALACE_VERSION_MINOR = PLAYPALACE_VERSION_PARTS[1] ?? 0;
export const PLAYPALACE_VERSION_PATCH = PLAYPALACE_VERSION_PARTS[2] ?? 0;

/** The version as the authorize packet spells it. */
export function versionDict() {
  return {
    major: PLAYPALACE_VERSION_MAJOR,
    minor: PLAYPALACE_VERSION_MINOR,
    patch: PLAYPALACE_VERSION_PATCH,
  };
}
