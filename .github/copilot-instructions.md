# Copilot Instructions

These guidelines will help GitHub Copilot generate code that is consistent with this Astro + TypeScript project’s patterns and best practices.

## 1. Project Structure

- Pages: `src/pages/` (use `.astro` or `.md` files with frontmatter for metadata).
- Layouts: `src/layouts/` (use `.astro` components for page wrappers).
- Components: `src/components/` (atomic, reusable `.astro` files).
- Utilities: `src/utils/` (TypeScript helper functions and scripts).
- Assets: `src/assets/` and `public/` for static files and optimized images.

## 2. Language & Syntax

- Use TypeScript with explicit types and interfaces.
- Prefer ES module syntax (`import/export`).
- Use `async/await` for asynchronous operations.

## 3. Styling & CSS

- Utilize Tailwind CSS classes exclusively in components.
- Avoid inline styles; update global styles in `styles/` directory if needed.

## 4. General

- Reuse existing utilities and components wherever possible.
- Follow the project’s directory structure and naming conventions.
