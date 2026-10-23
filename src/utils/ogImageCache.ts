import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

// Bump this when the OG template or font rendering changes.
const OG_IMAGE_CACHE_VERSION = "1";
const OG_IMAGE_CACHE_DIRECTORY = resolve(".cache/og-images");

interface OgImageCacheInput {
  id: string;
  title: string;
  author: string;
  siteTitle: string;
  body: string;
}

function getCachePath(cacheKey: string) {
  return resolve(OG_IMAGE_CACHE_DIRECTORY, `${cacheKey}.png`);
}

function isMissingFileError(error: unknown) {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    error.code === "ENOENT"
  );
}

export function createOgImageCacheKey(input: OgImageCacheInput) {
  return createHash("sha256")
    .update(
      JSON.stringify({
        version: OG_IMAGE_CACHE_VERSION,
        ...input,
      })
    )
    .digest("hex");
}

export async function readOgImageCache(cacheKey: string) {
  const cachePath = getCachePath(cacheKey);

  try {
    return new Uint8Array(await readFile(cachePath));
  } catch (error) {
    if (isMissingFileError(error)) {
      return null;
    }

    throw error;
  }
}

export async function writeOgImageCache(cacheKey: string, image: Uint8Array) {
  const cachePath = getCachePath(cacheKey);
  const temporaryPath = `${cachePath}.${process.pid}.tmp`;

  try {
    await mkdir(dirname(cachePath), { recursive: true });
    await writeFile(temporaryPath, image);
    await rename(temporaryPath, cachePath);
  } catch (error) {
    await rm(temporaryPath, { force: true }).catch(() => {});
    throw error;
  }
}
