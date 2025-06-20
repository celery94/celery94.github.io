import type { APIRoute } from "astro";
import { SITE } from "@/config";
import { getCollection } from "astro:content";

export const GET: APIRoute = async () => {
  const posts = await getCollection("blog");
  const lastModified = new Date().toISOString();
  
  // Get the latest post date for posts sitemap
  const latestPostDate = posts.reduce((latest, post) => {
    const postDate = post.data.modDatetime || post.data.pubDatetime;
    return postDate > latest ? postDate : latest;
  }, new Date(0));

  const sitemapIndex = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>${SITE.website}sitemap-0.xml</loc>
    <lastmod>${lastModified}</lastmod>
  </sitemap>
  <sitemap>
    <loc>${SITE.website}sitemap-posts.xml</loc>
    <lastmod>${latestPostDate.toISOString()}</lastmod>
  </sitemap>
  <sitemap>
    <loc>${SITE.website}sitemap-tags.xml</loc>
    <lastmod>${lastModified}</lastmod>
  </sitemap>
</sitemapindex>`;

  return new Response(sitemapIndex, {
    headers: {
      "Content-Type": "application/xml",
    },
  });
};
