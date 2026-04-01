import { unlink } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";
import {
  REPO_ROOT,
  collectOptimizableImages,
  createPipeline,
  formatBytes,
  readMetadata,
  toRepoPath,
  writeBuffer,
  writeLine,
  writeMarkdownReferenceUpdates,
} from "./image-utils.mjs";

const LOGO_PATH = path.join(REPO_ROOT, "public", "logo.png");

async function optimizeLogo(filePath, originalSize) {
  const buffer = await sharp(filePath)
    .rotate()
    .resize({
      width: 192,
      height: 192,
      fit: "inside",
      withoutEnlargement: false,
    })
    .png({
      compressionLevel: 9,
      palette: true,
    })
    .toBuffer();

  if (buffer.length >= originalSize) {
    return null;
  }

  return {
    action: "png",
    outputPath: filePath,
    buffer,
  };
}

async function optimizeTransparentPng(filePath, originalSize) {
  const webpBuffer = await createPipeline(filePath)
    .webp({ lossless: true, effort: 6 })
    .toBuffer();
  const pngBuffer = await createPipeline(filePath)
    .png({ compressionLevel: 9, palette: true })
    .toBuffer();
  const webpSavingsRatio = 1 - webpBuffer.length / originalSize;

  if (webpSavingsRatio >= 0.1 && webpBuffer.length < pngBuffer.length) {
    return {
      action: "webp-lossless",
      outputPath: filePath.replace(/\.png$/i, ".webp"),
      buffer: webpBuffer,
    };
  }

  if (pngBuffer.length >= originalSize) {
    return null;
  }

  return {
    action: "png",
    outputPath: filePath,
    buffer: pngBuffer,
  };
}

async function optimizeOpaqueImage(filePath, originalSize) {
  const webpBuffer = await createPipeline(filePath)
    .webp({ quality: 82, effort: 6 })
    .toBuffer();

  if (webpBuffer.length >= originalSize) {
    return null;
  }

  return {
    action: "webp",
    outputPath: filePath.replace(/\.(png|jpe?g)$/i, ".webp"),
    buffer: webpBuffer,
  };
}

async function chooseOptimization(image) {
  if (image.filePath === LOGO_PATH) {
    return optimizeLogo(image.filePath, image.size);
  }

  const metadata = await readMetadata(image.filePath);

  if (image.ext === ".png" && metadata.hasAlpha) {
    return optimizeTransparentPng(image.filePath, image.size);
  }

  return optimizeOpaqueImage(image.filePath, image.size);
}

async function main() {
  const candidates = await collectOptimizableImages();
  const markdownChanges = [];
  const sourceDeletes = [];
  let optimizedCount = 0;
  let savedBytes = 0;

  writeLine(`Found ${candidates.length} optimization candidates.`);

  for (const image of candidates) {
    const result = await chooseOptimization(image);

    if (!result) {
      writeLine(`skip   ${toRepoPath(image.filePath)} (${formatBytes(image.size)})`);
      continue;
    }

    const nextSize = result.buffer.length;
    const saved = image.size - nextSize;
    const oldExt = image.ext;
    const newExt = path.extname(result.outputPath).toLowerCase();

    if (result.outputPath === image.filePath) {
      await writeBuffer(result.outputPath, result.buffer);
    } else {
      await writeBuffer(result.outputPath, result.buffer);
      markdownChanges.push({
        sourcePath: image.filePath,
        oldExt,
        newExt,
      });
      sourceDeletes.push(image.filePath);
    }

    optimizedCount += 1;
    savedBytes += saved;

    writeLine(
      `write  ${result.action.padEnd(13)} ${toRepoPath(image.filePath)} -> ${toRepoPath(result.outputPath)} (${formatBytes(
        image.size
      )} -> ${formatBytes(nextSize)})`
    );
  }

  const markdownResult = await writeMarkdownReferenceUpdates(markdownChanges);

  for (const filePath of sourceDeletes) {
    await unlink(filePath);
  }

  writeLine();
  writeLine(`Optimized files: ${optimizedCount}`);
  writeLine(`Bytes saved: ${formatBytes(savedBytes)}`);
  writeLine(
    `Markdown files updated: ${markdownResult.updatedFiles} (${markdownResult.replacements} replacements)`
  );
}

main().catch(error => {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
  process.exitCode = 1;
});
