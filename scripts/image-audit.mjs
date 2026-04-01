import { collectImages, formatBytes, readMetadata, writeLine } from "./image-utils.mjs";

async function main() {
  const images = await collectImages();
  const byExtension = new Map();

  for (const image of images) {
    const current = byExtension.get(image.ext) ?? { count: 0, bytes: 0 };
    current.count += 1;
    current.bytes += image.size;
    byExtension.set(image.ext, current);
  }

  writeLine("Image inventory by extension:");
  for (const [ext, summary] of [...byExtension.entries()].sort((left, right) =>
    right[1].bytes - left[1].bytes
  )) {
    writeLine(
      `${ext.padEnd(5)} ${String(summary.count).padStart(4)} files  ${formatBytes(summary.bytes)}`
    );
  }

  writeLine();
  writeLine("Largest local images:");

  for (const image of images.slice(0, 25)) {
    const metadata = await readMetadata(image.filePath);
    const dimensions =
      metadata.width && metadata.height
        ? `${metadata.width}x${metadata.height}`
        : "unknown";
    const alpha = metadata.hasAlpha ? "alpha" : "opaque";

    writeLine(
      `${formatBytes(image.size).padStart(9)}  ${dimensions.padEnd(12)}  ${alpha.padEnd(6)}  ${image.repoPath}`
    );
  }
}

main().catch(error => {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
  process.exitCode = 1;
});
