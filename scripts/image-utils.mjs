import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const REPO_ROOT = path.resolve(__dirname, "..");
export const BLOG_ROOT = path.join(REPO_ROOT, "src", "data", "blog");
export const IMAGE_ROOTS = [
  path.join(REPO_ROOT, "src", "assets"),
  path.join(REPO_ROOT, "public"),
];

export const ALL_IMAGE_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".avif",
  ".gif",
  ".svg",
]);

export const OPTIMIZABLE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg"]);
export const MIN_OPTIMIZE_BYTES = 500 * 1024;
export const MAX_WIDTH = 1920;
export const MAX_HEIGHT = 4000;

export function writeLine(message = "") {
  process.stdout.write(`${message}\n`);
}

export function writeError(message) {
  process.stderr.write(`${message}\n`);
}

export function toRepoPath(filePath) {
  return path.relative(REPO_ROOT, filePath).split(path.sep).join("/");
}

export function formatBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export async function walkFiles(rootDir) {
  const entries = await fs.readdir(rootDir, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async entry => {
      const entryPath = path.join(rootDir, entry.name);
      if (entry.isDirectory()) {
        return walkFiles(entryPath);
      }

      return entry.isFile() ? [entryPath] : [];
    })
  );

  return files.flat();
}

export async function collectImages() {
  const allFiles = await Promise.all(IMAGE_ROOTS.map(root => walkFiles(root)));
  const imageFiles = allFiles
    .flat()
    .filter(filePath => ALL_IMAGE_EXTENSIONS.has(path.extname(filePath).toLowerCase()));

  const records = await Promise.all(
    imageFiles.map(async filePath => {
      const stats = await fs.stat(filePath);
      return {
        filePath,
        repoPath: toRepoPath(filePath),
        ext: path.extname(filePath).toLowerCase(),
        size: stats.size,
      };
    })
  );

  return records.sort((left, right) => right.size - left.size);
}

export async function collectOptimizableImages() {
  const images = await collectImages();
  return images.filter(
    image =>
      OPTIMIZABLE_EXTENSIONS.has(image.ext) && image.size >= MIN_OPTIMIZE_BYTES
  );
}

export async function readMetadata(filePath) {
  return sharp(filePath).metadata();
}

export function createPipeline(filePath) {
  return sharp(filePath).rotate().resize({
    width: MAX_WIDTH,
    height: MAX_HEIGHT,
    fit: "inside",
    withoutEnlargement: true,
  });
}

export async function ensureDir(filePath) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
}

export async function writeBuffer(targetPath, buffer) {
  await ensureDir(targetPath);
  await fs.writeFile(targetPath, buffer);
}

export async function writeMarkdownReferenceUpdates(changes) {
  if (changes.length === 0) {
    return { updatedFiles: 0, replacements: 0 };
  }

  const changeByPath = new Map(
    changes.map(change => [
      path.normalize(change.sourcePath),
      {
        oldExt: change.oldExt,
        newExt: change.newExt,
      },
    ])
  );

  const markdownFiles = (await walkFiles(BLOG_ROOT)).filter(filePath =>
    filePath.endsWith(".md")
  );

  let updatedFiles = 0;
  let replacements = 0;

  for (const markdownFile of markdownFiles) {
    const original = await fs.readFile(markdownFile, "utf8");
    let didChange = false;

    const next = original.replace(
      /((?:\.\.\/|\.\/)[^"'()\s>]+?\.(?:png|jpe?g))/gi,
      match => {
        const resolved = path.resolve(path.dirname(markdownFile), match);
        const change = changeByPath.get(path.normalize(resolved));

        if (!change) {
          return match;
        }

        if (!match.toLowerCase().endsWith(change.oldExt)) {
          return match;
        }

        didChange = true;
        replacements += 1;
        return `${match.slice(0, -change.oldExt.length)}${change.newExt}`;
      }
    );

    if (!didChange || next === original) {
      continue;
    }

    await fs.writeFile(markdownFile, next);
    updatedFiles += 1;
  }

  return { updatedFiles, replacements };
}
