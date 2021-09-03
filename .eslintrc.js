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
  plugins: [
    'html',
    'simple-import-sort',
    'vue',
  ],
  rules: {
    camelcase: 'off',
    'func-style': ['error', 'declaration'],
    'import/extensions': 'off',
    'import/order': 'off',
    'max-len': ['error', { code: 120 }],
    'no-alert': 'off',
    'no-console': 'off',
    'no-extra-parens': ['error', 'all'],
    // modified https://github.com/airbnb/javascript/blob/master/packages/eslint-config-airbnb-base/rules/style.js#L339
    // In our opinion, readability comes first and ForOF statements are more readable,
    // so we remove the ForOfStatement block.
    'no-restricted-syntax': [
      'error',
      {
        selector: 'ForInStatement',
        message: ('for..in loops iterate over the entire prototype chain, which is virtually never what you want.'
          + 'Use Object.{keys,values,entries}, and iterate over the resulting array.'),
      },
      {
        selector: 'LabeledStatement',
        message: 'Labels are a form of GOTO; using them makes code confusing and hard to maintain and understand.',
      },
      {
        selector: 'WithStatement',
        message: '`with` is disallowed in strict mode because it makes code impossible to predict and optimize.',
      },
    ],
    'no-shadow': 'off',
    'no-useless-constructor': 'off',
    semi: ['error', 'never'],
    'simple-import-sort/exports': 'error',
    'simple-import-sort/imports': 'error',
    'sort-imports': 'off',
    '@typescript-eslint/no-useless-constructor': ['error'],
    '@typescript-eslint/no-shadow': ['error'],
    '@typescript-eslint/explicit-function-return-type': ['error', { allowExpressions: true }],
    'vue/valid-v-slot': ['error', { allowModifiers: true }],
  },
}
