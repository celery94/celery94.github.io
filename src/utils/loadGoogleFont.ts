import { access, readFile } from "node:fs/promises";

let hasWarnedAboutFontFallback = false;

const LOCAL_FONT_CANDIDATES = {
  normal: [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
  ],
  bold: [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/consolab.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
  ],
} as const;

function warnFontFallback(message: string) {
  if (hasWarnedAboutFontFallback) {
    return;
  }

  hasWarnedAboutFontFallback = true;
  process.stderr.write(`${message}\n`);
}

async function readFirstAvailableFont(paths: readonly string[]) {
  for (const filePath of paths) {
    try {
      await access(filePath);
      return readFile(filePath);
    } catch {
      continue;
    }
  }

  return null;
}

async function loadLocalFallbackFonts() {
  const [normalFont, boldFont] = await Promise.all([
    readFirstAvailableFont(LOCAL_FONT_CANDIDATES.normal),
    readFirstAvailableFont(LOCAL_FONT_CANDIDATES.bold),
  ]);

  const fonts = [];

  if (normalFont) {
    fonts.push({
      name: "System Fallback",
      data: Uint8Array.from(normalFont).buffer,
      weight: 400,
      style: "normal",
    });
  }

  if (boldFont) {
    fonts.push({
      name: "System Fallback",
      data: Uint8Array.from(boldFont).buffer,
      weight: 700,
      style: "bold",
    });
  }

  if (fonts.length === 0) {
    throw new Error("No local fallback fonts were found for OG image generation.");
  }

  return fonts;
}

async function loadGoogleFont(
  font: string,
  text: string,
  weight: number
): Promise<ArrayBuffer> {
  const API = `https://fonts.googleapis.com/css2?family=${font}:wght@${weight}&text=${encodeURIComponent(text)}`;

  const cssResponse = await fetch(API, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; de-at) AppleWebKit/533.21.1 (KHTML, like Gecko) Version/5.0.5 Safari/533.21.1",
    },
    signal: AbortSignal.timeout(5000),
  });

  if (!cssResponse.ok) {
    throw new Error(`Failed to download Google Fonts CSS. Status: ${cssResponse.status}`);
  }

  const css = await cssResponse.text();

  const resource = css.match(
    /src: url\((.+?)\) format\('(opentype|truetype)'\)/
  );

  if (!resource) throw new Error("Failed to download dynamic font");

  const res = await fetch(resource[1], {
    signal: AbortSignal.timeout(5000),
  });

  if (!res.ok) {
    throw new Error("Failed to download dynamic font. Status: " + res.status);
  }

  return res.arrayBuffer();
}

async function loadGoogleFonts(
  text: string
): Promise<
  Array<{ name: string; data: ArrayBuffer; weight: number; style: string }>
> {
  const fontsConfig = [
    {
      name: "IBM Plex Mono",
      font: "IBM+Plex+Mono",
      weight: 400,
      style: "normal",
    },
    {
      name: "IBM Plex Mono",
      font: "IBM+Plex+Mono",
      weight: 700,
      style: "bold",
    },
  ];

  const fontResults = await Promise.allSettled(
    fontsConfig.map(async ({ name, font, weight, style }) => {
      const data = await loadGoogleFont(font, text, weight);
      return { name, data, weight, style };
    })
  );

  const fonts = fontResults.flatMap(result =>
    result.status === "fulfilled" ? [result.value] : []
  );

  if (fonts.length !== fontsConfig.length) {
    warnFontFallback(
      "Falling back to local system fonts because Google Fonts could not be downloaded during OG image generation."
    );
  }

  return fonts.length > 0 ? fonts : loadLocalFallbackFonts();
}

export default loadGoogleFonts;
