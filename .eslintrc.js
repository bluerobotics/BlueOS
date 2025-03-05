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
    'import',
    'simple-import-sort',
    'vue',
  ],
  ignorePatterns: ['**/src/libs/MAVLink2Rest/mavlink2rest-ts/**'],
  rules: {
    camelcase: 'off',
    indent: ['error', 2, { SwitchCase: 1 }],
    'func-style': ['error', 'declaration'],
    'import/extensions': 'off',
    'import/order': 'off',
    'import/no-unresolved': 'error',
    'max-len': ['error', { code: 120 }],
    'no-alert': 'off',
    'no-bitwise': 'off',
    'no-console': 'off',
    'no-continue': 'off',
    'no-else-return': ['error', { allowElseIf: false }],
    'no-extra-parens': ['error', 'all'],
    'no-mixed-operators': 'off',
    // modified https://github.com/airbnb/javascript/blob/master/packages/eslint-config-airbnb-base/rules/style.js#L339
    // In our opinion, readability comes first and ForOF statements are more readable,
    // so we remove the ForOfStatement block.
    'no-restricted-syntax': [
      'error',
      {
        selector: 'ForInStatement',
        message: 'for..in loops iterate over the entire prototype chain, which is virtually never what you want.'
          + 'Use Object.{keys,values,entries}, and iterate over the resulting array.',
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
    'no-param-reassign': 'off',
    'no-shadow': 'off',
    'no-use-before-define': 'off',
    'no-useless-constructor': 'off',
    semi: ['error', 'never'],
    'simple-import-sort/exports': 'error',
    'simple-import-sort/imports': 'error',
    'sort-imports': 'off',
    '@typescript-eslint/no-useless-constructor': ['error'],
    '@typescript-eslint/no-non-null-assertion': 'off',
    '@typescript-eslint/no-shadow': ['error'],
    '@typescript-eslint/explicit-function-return-type': ['error', { allowExpressions: true }],
    // Need to disable base rule to apply pattern of unused variables
    'no-unused-vars': 'off',
    '@typescript-eslint/no-unused-vars': [
      'warn',
      {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      },
    ],
    // Disable to avoid conflicts with eslint max-len
    'vue/max-len': 'off',
    'vue/multi-word-component-names': 'off',
    'vue/no-unused-properties': ['error', {
      groups: ['props', 'data', 'computed', 'methods', 'setup'],
      deepData: true,
      ignorePublicMembers: false,
    }],
    // We don't care about `noopener noreferrer`
    'vue/no-template-target-blank': 'off',
    'vue/no-v-text-v-html-on-component': 'off',
    'vue/valid-v-slot': ['error', { allowModifiers: true }],
    // Disable accessibility checks
    'vuejs-accessibility/alt-text': 'off',
    'vuejs-accessibility/anchor-has-content': 'off',
    'vuejs-accessibility/mouse-events-have-key-events': 'off',
    'no-await-in-loop': 'off',
  },
  settings: {
    'import/resolver': {
      typescript: {
        alwaysTryTypes: true,
        project: './tsconfig.json',
      },
      node: {
        extensions: ['.js', '.json', '.jsx', '.ts', '.tsx', '.vue'],
      },
      vite: {
        viteConfig: require('./vite.config').viteConfigObj, // named export of the Vite config object.
      },
    },
  },
}
