import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["node_modules", "../custom_components"] },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: { allowDefaultProject: ["*.js", "*.mjs"] } },
    },
  },
  { files: ["*.js", "*.mjs"], ...tseslint.configs.disableTypeChecked },
  { files: ["test/**"], rules: { "@typescript-eslint/no-non-null-assertion": "off" } },
);
