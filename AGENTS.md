# Repository Guidelines

## Project Structure & Module Organization
This repository is an Astro-based content site. Route files live in `src/pages/`, shared UI in `src/components/`, layouts in `src/layouts/`, reusable helpers in `src/utils/`, and global styling in `src/styles/`. Markdown articles are stored in `src/data/blog/`, while processed images belong in `src/assets/` and static passthrough files belong in `public/`. Repo-specific agent skills live under `.agents/skills/`.

## Build, Test, and Development Commands
Install dependencies with `npm install`. Use `npm run dev` for local development, `npm run preview` to inspect the production build, and `npm run sync` after changing content schemas or Astro types. Run `npm run lint` for ESLint checks, `npm run format:check` to verify Prettier output, and `npm run format` to rewrite files. Do not run `npm run build` by default for routine article creation; reserve it for changes that affect Astro config, content schemas, routing, search/Pagefind behavior, shared UI/layout code, or when the user explicitly asks for a production build. Before merging, `npm run build` remains the production validation command; it runs `astro check`, builds the site, generates Pagefind search indexes, and copies them into `public/pagefind/`.

## Content Workflow
When creating a new article from an external URL, use the `Create Blog Post From URL` skill by default. Follow that skill's workflow for browser-based source extraction, Chinese article drafting, article numbering, frontmatter, cover handling under `src/assets/{ID}/`, references, and optional WeChat draft publishing. For article-only changes, prefer targeted validation such as Prettier checks on the new Markdown and JSON files instead of a full production build unless build-affecting files changed.

## Coding Style & Naming Conventions
Prettier is the source of truth: 2-space indentation, semicolons, double quotes, 80-character line width, and Tailwind class sorting via `prettier-plugin-tailwindcss`. ESLint includes Astro and TypeScript rules and rejects `console` calls. Use the `@/*` import alias for `src` modules when it improves readability. Keep Astro components and layouts in PascalCase (`Header.astro`), utilities in camelCase (`getSortedPosts.ts`), and content filenames descriptive and kebab-case with numeric prefixes when following the existing article sequence (for example `590-github-copilot-cli-for-beginners.md`).

## Testing Guidelines
There is no separate unit-test suite in this repository today. Treat `npm run lint` as the required validation baseline for code and UI changes. For article-only work, run targeted formatting checks on the changed Markdown/JSON files and use `npm run dev` only when a browser smoke test is needed. Confirm search after a production build only when search content, Pagefind output, routing, or shared rendering behavior changed.

## Commit & Pull Request Guidelines
Recent history uses Conventional Commits such as `feat: ...`, `fix: ...`, and `refactor: ...`; `cz.yaml` is configured for `cz_conventional_commits`, so keep that format. Pull requests should include a short summary, note any changed routes or content collections, link the related issue when one exists, and attach screenshots for visible UI changes. Do not merge with failing GitHub Pages build checks.
