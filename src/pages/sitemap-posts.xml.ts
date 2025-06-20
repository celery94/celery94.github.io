import type { APIRoute } from "astro";
import type { CollectionEntry } from "astro:content";
import { SITE } from "@/config";
import { getCollection } from "astro:content";
import getSortedPosts from "@/utils/getSortedPosts";

export const GET: APIRoute = async () => {
  const posts = await getCollection("blog");
  const sortedPosts = getSortedPosts(posts);

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sortedPosts
  .map((post: CollectionEntry<"blog">) => {
    const lastmod = post.data.modDatetime || post.data.pubDatetime;
    return `  <url>
    <loc>${SITE.website}posts/${post.id}/</loc>
    <lastmod>${lastmod.toISOString()}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
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
