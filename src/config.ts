export const SITE = {
  website: "https://celery94.github.io/", // replace this with your deployed domain
  author: "Celery Liu",
  profile: "https://celery94.github.io/",
  desc: "A minimal, responsive and SEO-friendly Astro blog theme.",
  title: "Assistant Hub",
  ogImage: "astropaper-og.jpg",
  lightAndDarkMode: true,
  postPerIndex: 10,
  postPerPage: 10,
  scheduledPostMargin: 15 * 60 * 1000, // 15 minutes
  showArchives: true,
  showBackButton: true, // show back button in post detail
  editPost: {
    url: "https://github.com/satnaing/astro-paper/edit/main/src/content/blog",
    text: "Suggest Changes",
    appendFilePath: true,
  },
  dynamicOgImage: true,
} as const;
