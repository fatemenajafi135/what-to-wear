import nextPlugin from "@next/eslint-plugin-next";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

/*
 * Flat config built directly from each plugin's own flat export, rather
 * than through `eslint-config-next`'s FlatCompat("next/core-web-vitals")
 * path — that combination crashes ESLint 9/10 with a circular-JSON error
 * while formatting an internal config-validation message (a real bug in
 * the FlatCompat + current eslint-plugin-react-hooks/react combination,
 * not something this project can fix). `eslint-plugin-react-hooks`'s own
 * bundled "configs" export is similarly circular when serialized, so its
 * rules are listed explicitly below instead of spreading a packaged config.
 */
const eslintConfig = [
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      "playwright-report/**",
      "test-results/**",
    ],
  },
  ...tseslint.configs.recommended,
  jsxA11y.flatConfigs.recommended,
  {
    plugins: {
      "@next/next": nextPlugin,
      "react-hooks": reactHooks,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
];

export default eslintConfig;
