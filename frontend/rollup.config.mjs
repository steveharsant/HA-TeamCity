import resolve from "@rollup/plugin-node-resolve";
import terser from "@rollup/plugin-terser";
import typescript from "@rollup/plugin-typescript";

export default {
  input: "src/teamcity-card.ts",
  output: {
    file: "../custom_components/teamcity/frontend/teamcity-card.js",
    format: "es",
    sourcemap: false,
  },
  plugins: [
    resolve(),
    typescript({ tsconfig: "./tsconfig.json", include: ["src/**/*.ts"], noEmitOnError: true }),
    terser({ format: { comments: false } }),
  ],
};
