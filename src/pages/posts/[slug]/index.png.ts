import type { APIRoute } from "astro";
import { getCollection, type CollectionEntry } from "astro:content";
import { generateOgImageForPost } from "@/utils/generateOgImages";
import {
  createOgImageCacheKey,
  readOgImageCache,
  writeOgImageCache,
} from "@/utils/ogImageCache";
import { slugifyStr } from "@/utils/slugify";
import { SITE } from "@/config";

export async function getStaticPaths() {
  if (!SITE.dynamicOgImage) {
    return [];
  }

  const posts = await getCollection("blog").then(p =>
    p.filter(({ data }) => !data.draft && !data.ogImage)
  );

  return posts.map(post => ({
    params: { slug: slugifyStr(post.data.title) },
    props: post,
  }));
}

export const GET: APIRoute = async ({ props }) => {
  if (!SITE.dynamicOgImage) {
    return new Response(null, {
      status: 404,
      statusText: "Not found",
    });
  }

  const post = props as CollectionEntry<"blog">;
  const cacheKey = createOgImageCacheKey({
    id: post.id,
    title: post.data.title,
    author: post.data.author,
    siteTitle: SITE.title,
    body: post.body ?? "",
  });
  const cachedImage = await readOgImageCache(cacheKey);
  const image = cachedImage ?? (await generateOgImageForPost(post));

  if (!cachedImage) {
    await writeOgImageCache(cacheKey, image);
  }

  return new Response(image, {
    headers: { "Content-Type": "image/png" },
  });
};
