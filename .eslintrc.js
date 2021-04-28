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
    indent: ['error', 2],
    'linebreak-style': ['error', 'unix'],
    quotes: ['error', 'single'],
    semi: ['error', 'never'],
    camelcase: [2, { properties: 'always' }],
    'space-before-function-paren': ['error', 'always'],
    'no-extra-parens': ['error', 'all'],
  },
}
