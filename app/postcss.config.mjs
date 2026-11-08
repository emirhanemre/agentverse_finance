import { fileURLToPath } from "node:url";

/** @type {import('postcss-load-config').Config} */
const config = {
  plugins: {
    tailwindcss: { config: fileURLToPath(new URL("./tailwind.config.ts", import.meta.url)) },
  },
};

export default config;
