import type { APIRoute } from "astro";
import { SITE } from "@/config";
import { getCollection } from "astro:content";
import getUniqueTags from "@/utils/getUniqueTags";

export const GET: APIRoute = async () => {
  const posts = await getCollection("blog");
  const tags = getUniqueTags(posts);
  const lastModified = new Date().toISOString();

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${SITE.website}tags/</loc>
    <lastmod>${lastModified}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
${tags
  .map((tagObj: { tag: string; tagName: string }) => {
    return `  <url>
    <loc>${SITE.website}tags/${tagObj.tag}/</loc>
    <lastmod>${lastModified}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>`;
  })
  .join("\n")}
</urlset>`;

  return new Response(sitemap, {
    headers: {
      "Content-Type": "application/xml",
    },
  });
};
