import type { APIRoute } from "astro";
import type { CollectionEntry } from "astro:content";
import { SITE } from "@/config";
import { getCollection } from "astro:content";
import getSortedPosts from "@/utils/getSortedPosts";
import getUniqueTags from "@/utils/getUniqueTags";

export const GET: APIRoute = async () => {
  const posts = await getCollection("blog");
  const sortedPosts = getSortedPosts(posts);
  const tags = getUniqueTags(posts);
  const lastModified = new Date().toISOString();

  // Static pages URLs
  const staticPages = [
    {
      url: `${SITE.website}`,
      lastmod: lastModified,
      changefreq: "daily",
      priority: "1.0"
    },
    {
      url: `${SITE.website}about/`,
      lastmod: lastModified,
      changefreq: "monthly",
      priority: "0.8"
    },
    {
      url: `${SITE.website}search/`,
      lastmod: lastModified,
      changefreq: "weekly",
      priority: "0.7"
    },
    {
      url: `${SITE.website}tags/`,
      lastmod: lastModified,
      changefreq: "weekly",
      priority: "0.7"
    },
    {
      url: `${SITE.website}archives/`,
      lastmod: lastModified,
      changefreq: "weekly", 
      priority: "0.7"
    }
  ];

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${staticPages
  .map(page => `  <url>
    <loc>${page.url}</loc>
    <lastmod>${page.lastmod}</lastmod>
    <changefreq>${page.changefreq}</changefreq>
    <priority>${page.priority}</priority>
  </url>`)
  .join("\n")}
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
