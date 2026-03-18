# Repository Guidelines

## Project Structure & Module Organization
This repository is an Astro-based content site. Route files live in `src/pages/`, shared UI in `src/components/`, layouts in `src/layouts/`, reusable helpers in `src/utils/`, and global styling in `src/styles/`. Markdown articles are stored in `src/data/blog/`, while processed images belong in `src/assets/` and static passthrough files belong in `public/`. Repo-specific agent skills live under `.agents/skills/`.

## Build, Test, and Development Commands
Install dependencies with `npm install`. Use `npm run dev` for local development, `npm run preview` to inspect the production build, and `npm run sync` after changing content schemas or Astro types. Run `npm run lint` for ESLint checks, `npm run format:check` to verify Prettier output, and `npm run format` to rewrite files. Use `npm run build` before merging; it runs `astro check`, builds the site, generates Pagefind search indexes, and copies them into `public/pagefind/`.

## Coding Style & Naming Conventions
Prettier is the source of truth: 2-space indentation, semicolons, double quotes, 80-character line width, and Tailwind class sorting via `prettier-plugin-tailwindcss`. ESLint includes Astro and TypeScript rules and rejects `console` calls. Use the `@/*` import alias for `src` modules when it improves readability. Keep Astro components and layouts in PascalCase (`Header.astro`), utilities in camelCase (`getSortedPosts.ts`), and content filenames descriptive and kebab-case with numeric prefixes when following the existing article sequence (for example `590-github-copilot-cli-for-beginners.md`).

## Testing Guidelines
There is no separate unit-test suite in this repository today. Treat `npm run lint` as the required validation baseline for every change. For content or UI work, also smoke-test the affected route in `npm run dev` and confirm search still works after a production build.

## Commit & Pull Request Guidelines
Recent history uses Conventional Commits such as `feat: ...`, `fix: ...`, and `refactor: ...`; `cz.yaml` is configured for `cz_conventional_commits`, so keep that format. Pull requests should include a short summary, note any changed routes or content collections, link the related issue when one exists, and attach screenshots for visible UI changes. Do not merge with failing GitHub Pages build checks.
