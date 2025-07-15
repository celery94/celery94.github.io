# Copilot Instructions

## Project Overview

- Astro v5.7 static site generator with TypeScript for a knowledge-sharing blog (Aide Hub).
- Entry configuration: `astro.config.ts` (site URL, markdown plugins, Tailwind integration via `@tailwindcss/vite`).

## Directory & Architecture

- `src/pages/`: routes and endpoints (`index.astro`, `search.astro`, dynamic folders under `archives/`, `posts/`, `tags/`).
- `src/layouts/`: reusable page wrappers (`Layout.astro`, `Main.astro`, `PostDetails.astro`, `AboutLayout.astro`).
- `src/components/`: UI components (`Header.astro`, `Card.astro`, `Pagination.astro`, `EditPost.astro`, etc.).
- `src/data/blog/`: Markdown posts; `src/content.config.ts` defines Zod schema for frontmatter.
- `styles/`: global CSS with Tailwind directives (`global.css`), custom effects, typography and dark-mode styles.

## Styling with Tailwind CSS v4

- Configured in `vite.plugins` via `tailwindcss()` in `astro.config.ts`.
- Use `@import "tailwindcss/base"`, `@import "tailwindcss/components"`, `@import "tailwindcss/utilities"` in `styles/global.css`.
- Additional Tailwind plugins: `@tailwindcss/typography` (configured via Vite plugin).

## Build & Development Workflow

- `npm run dev`: starts Astro dev server.
- `npm run build`: runs `astro check && astro build`, then `pagefind --site dist` to index search and copies output to `public/pagefind/`.
- `npm run preview`: preview production build.
- Lint: `npm run lint` (ESLint with `eslint-plugin-astro`, TypeScript parser).
- Format: `npm run format` / `npm run format:check` (Prettier with Astro & Tailwind plugins).

## Deployment & CI

- GitHub Actions workflow in `.github/workflows/static.yml`:
  - Build with `withastro/action@v2` on Node.js (default 18).
  - Deploy to GitHub Pages via `actions/deploy-pages@v4`.
- Ensure branch is `main` or adjust workflow triggers accordingly.

## Content & Data Patterns

- Posts loaded from `src/data/blog/` via `astro:content` loader; schema enforces `author`, `pubDatetime`, `tags`, `draft`, `description`, etc.
- Slug-based routing maps filenames to URLs under `/posts/:slug`.
- Pagination and tag filtering using utilities in `src/utils/` (`getSortedPosts.ts`, `getPostsByTag.ts`, `getPostsByGroupCondition.ts`).

## Open Graph & SEO

- Dynamic OG image generation in `src/utils/generateOgImages.ts`, using `@resvg/resvg-js` and `satori` with templates in `src/utils/og-templates`.
- OG image endpoints: `src/pages/og.png.ts` and dynamic handlers for each post.
- Sitemap and RSS via `@astrojs/sitemap` and `@astrojs/rss`, configured in `astro.config.ts`.

## TypeScript & Aliases

- `tsconfig.json` maps `@/*` to `src/*`; import modules with `@/path/to/file`.
- All `.astro` and `.ts` files use strict typing; catch type errors via `astro check` in build script.

## Search & Indexing

- `pagefind` powered on-site search: invoked in `npm run build`, output placed in `public/pagefind`.
- Search UI provided by `@pagefind/default-ui` (imported in layouts).

---

_Review these instructions and suggest additions or clarifications for any missing project-specific patterns._
