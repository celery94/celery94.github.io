export const SITE = {
  website: "https://celery94.github.io/", // replace this with your deployed domain
  author: "Celery Liu",
  profile: "https://celery94.github.io/",
  desc: "Aide Hub - A technical blog focused on AI assistants, software development, and technology insights by Celery Liu",
  title: "Aide Hub",
  ogImage: "astropaper-og.jpg",
  lightAndDarkMode: true,
  postPerIndex: 10,
  postPerPage: 9,
  scheduledPostMargin: 15 * 60 * 1000, // 15 minutes
  showArchives: true,
  showBackButton: true, // show back button in post detail
  editPost: {
    disabled: false,
    url: "",
    text: "Suggest Changes",
    appendFilePath: true,
  },
  dynamicOgImage: true,
} as const;
