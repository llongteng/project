import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // useEffect + fetch + setState is a widely-used pattern.
      // The alternative (Suspense + use hook) requires architectural changes
      // disproportionate to Phase 1 scope.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
