// The web client's own version.
//
// This is the single source of truth for the browser client's version. It is
// deliberately *not* read from the server: an older server still reports its
// own number, and showing that made this client look out of date when it was
// not.
//
// Note this is separate from version.js, which is a cache-busting token loaded
// as a classic script by index.html and holds no version number.

export const PLAYPALACE_VERSION = "12.0.0";

export const PLAYPALACE_VERSION_MAJOR = Number(PLAYPALACE_VERSION.split(".")[0]);
export const PLAYPALACE_VERSION_MINOR = Number(PLAYPALACE_VERSION.split(".")[1]);
export const PLAYPALACE_VERSION_PATCH = Number(PLAYPALACE_VERSION.split(".")[2]);

/** The version as the authorize packet spells it. */
export function versionDict() {
  return {
    major: PLAYPALACE_VERSION_MAJOR,
    minor: PLAYPALACE_VERSION_MINOR,
    patch: PLAYPALACE_VERSION_PATCH,
  };
}