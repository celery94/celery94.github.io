import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import getSortedPosts from "@/utils/getSortedPosts";
import { SITE } from "@/config";
import sanitizeHtml from "sanitize-html";
import { marked } from "marked";

export async function GET() {
  const posts = await getCollection("blog");
  const sortedPosts = getSortedPosts(posts);
  
  return rss({
    title: SITE.title,
    description: SITE.desc,
    site: SITE.website,
    items: await Promise.all(
      sortedPosts.map(async ({ data, body, id }) => {
        // 将Markdown转换为HTML提供更丰富的内容
        const content = sanitizeHtml(marked.parse(body));
        
        return {
          link: `posts/${id}/`,
          title: data.title,
          description: data.description,
          pubDate: new Date(data.modDatetime ?? data.pubDatetime),
          content,
          // 添加文章作者信息
          author: SITE.author,
          // 添加分类信息 - 使用tags作为分类
          categories: data.tags || [],
          // 添加自定义数据
          customData: `
            ${data.ogImage ? `<media:content url="${new URL(`/posts/${id}/${data.ogImage}`, SITE.website)}" medium="image" />` : ''}
            <language>zh-cn</language>
          `
        };
      })
    ),
    // 自定义RSS feed属性
    customData: `
      <language>zh-cn</language>
      <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
      <image>
        <url>${new URL('/logo.png', SITE.website)}</url>
        <title>${SITE.title}</title>
        <link>${SITE.website}</link>
      </image>
      <copyright>Copyright ${new Date().getFullYear()} ${SITE.author}</copyright>
      <ttl>60</ttl>
    `,
    stylesheet: '/rss/styles.xsl',
  });
}
