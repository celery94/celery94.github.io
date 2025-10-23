# Copilot Instructions

## Project Overview

- **Aide Hub**: Astro v5.7 static site generator with TypeScript for a bilingual technical blog (Chinese/English)
- **Core Purpose**: Knowledge sharing platform for software development, AI tools, and programming content
- **Author**: Celery Liu - focused on .NET, Azure, AI assistants, and modern development practices

## Architecture & Key Patterns

### Content Management Strategy

- **Blog Posts**: All content in `src/data/blog/` as numbered markdown files (001-xxx.md, 002-xxx.md)
- **Content Schema**: Zod validation in `src/content.config.ts` enforces `author`, `pubDatetime`, `tags`, `draft`, `description`, `ogImage`
- **Frontmatter Pattern**: Required fields include `pubDatetime` (Date), `title`, `description`, `tags` array
- **Asset Organization**: Images stored in `src/assets/` with numbered subdirectories matching post numbers

### Routing & URL Structure

- **Posts**: `/posts/[slug]/` via `src/pages/posts/[slug]/index.astro`
- **Dynamic Pages**: Collections use `getStaticPaths()` with slug-based routing from filename
- **Archives**: Time-based pagination in `/archives/[...page].astro`
- **Tags**: Category filtering via `/tags/[tag]/[...page].astro`

### Styling Architecture

- **Tailwind CSS v4**: Configured via Vite plugin, not traditional config file
- **CSS Imports**: `@import "tailwindcss"` in `src/styles/global.css` (no separate base/components/utilities)
- **Theme System**: CSS custom properties for light/dark modes with enhanced contrast ratios
- **Modular Styles**: Separate files for typography, animations, dark themes, code highlighting

## Essential Development Commands

```bash
# Development with TypeScript checking
npm run dev

# Production build with search indexing
npm run build  # Runs: astro check && astro build && pagefind --site dist && cp -r dist/pagefind public/

# Format code (Prettier + Astro + Tailwind plugins)
npm run format

# Lint with Astro-specific rules
npm run lint
```

## Critical Build Dependencies

- **Search**: `pagefind` generates client-side search index, requires build step to copy to `public/pagefind/`
- **OG Images**: Dynamic generation using `@resvg/resvg-js` + `satori` with custom templates in `src/utils/og-templates/`
- **Markdown**: `remark-toc` + `remark-collapse` for table of contents and collapsible sections

## Content Utilities & Helpers

- **Post Sorting**: `getSortedPosts()` - filters drafts, sorts by `modDatetime` or `pubDatetime`
- **Tag Filtering**: `getPostsByTag()` and `getPostsByGroupCondition()` for category pages
- **Slug Generation**: Uses filename as slug via Astro's content collection loader

## SEO & Performance

- **Structured Data**: BlogPosting schema in `Layout.astro` with dynamic fields
- **Responsive Images**: Astro's experimental responsive images enabled
- **Meta Tags**: Dynamic generation based on post frontmatter and SITE config
- **Sitemap**: Auto-generated with archive page filtering based on `SITE.showArchives`

## Development Patterns

- **Import Aliases**: Use `@/` prefix for all src imports (configured in `tsconfig.json`)
- **Component Props**: Always export interface Props for type safety in Astro components
- **Asset References**: Use `src/assets/` for images, reference via frontmatter `ogImage` field
- **Config Management**: Centralized in `src/config.ts` with SITE object for all global settings

## Deployment & CI

- **Platform**: GitHub Pages via Actions workflow
- **Trigger**: Push to `main` branch or manual dispatch
- **Build Tool**: `withastro/action@v2` handles Node.js setup and build process
- **Static Output**: All content pre-rendered at build time
