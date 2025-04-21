import type { APIRoute } from "astro";

const getRobotsTxt = (sitemapURL: URL) => `
# robots.txt for Assistant Hub
# https://celery94.github.io/

User-agent: *
Allow: /
Disallow: /admin/
Disallow: /draft/
Disallow: /api/
Disallow: /*?

# Allow specific bots with custom rules
User-agent: Googlebot
Allow: /
Crawl-delay: 1

User-agent: Bingbot
Allow: /
Crawl-delay: 1

User-agent: Baiduspider
Allow: /
Crawl-delay: 2

# Sitemap
Sitemap: ${sitemapURL.href}
`;

export const GET: APIRoute = ({ site }) => {
  const sitemapURL = new URL("sitemap-index.xml", site);
  return new Response(getRobotsTxt(sitemapURL));
};
