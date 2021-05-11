/*global module*/
module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  extends: ['eslint:recommended', 'plugin:vue/vue3-strongly-recommended'],
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
    'object-shorthand': 'error',
    'prefer-const': 'error',
    'space-before-function-paren': ['error', 'always'],
    indent: ['error', 2],
    quotes: ['error', 'single'],
    semi: ['error', 'never'],
  },
}
