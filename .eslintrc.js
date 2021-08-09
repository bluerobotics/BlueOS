/*global module*/
module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/recommended',
    '@vue/typescript/recommended',
  ],
  parserOptions: {
    ecmaVersion: 12,
  },
  plugins: ['vue', 'html'],
  rules: {
    'arrow-parens': ['error', 'always'],
    'comma-dangle': ['error', 'always-multiline'],
    'func-style': ['error', 'declaration'],
    'linebreak-style': ['error', 'unix'],
    'max-len': ['error', { 'code': 120 }],
    'no-extra-parens': ['error', 'all'],
    'no-multi-spaces': 'error',
    'object-curly-spacing': ['error', 'always'],
    'object-shorthand': 'error',
    'prefer-const': 'error',
    'sort-imports': 'error',
    'space-before-function-paren': ['error', 'always'],
    indent: ['error', 2, { 'SwitchCase': 1 }],
    quotes: ['error', 'single'],
    semi: ['error', 'never'],
  },
}
