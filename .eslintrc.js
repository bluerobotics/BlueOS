module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/recommended',
    '@vue/airbnb',
    '@vue/typescript/recommended',
  ],
  parserOptions: {
    ecmaVersion: 12,
  },
  plugins: ['vue', 'html'],
  rules: {
    camelcase: 'off',
    'func-style': ['error', 'declaration'],
    'max-len': ['error', { code: 120 }],
    'no-extra-parens': ['error', 'all'],
    'sort-imports': 'error',
    semi: ['error', 'never'],
    'import/order': 'off',
    'no-alert': 'off',
    'no-console': 'off',
  },
}
