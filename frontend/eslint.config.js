import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default [
  { ignores: ['dist/**', 'node_modules/**', 'coverage/**', 'src/types/api.ts', 'openapi.json'] },
  { languageOptions: { ecmaVersion: 'latest', sourceType: 'module' } },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      globals: { ...globals.browser },
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
  {
    files: ['scripts/**/*.js', '*.config.{js,ts}'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
  // Must stay last: turns off every rule Prettier already handles.
  prettier,
]
