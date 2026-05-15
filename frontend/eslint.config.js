import js from '@eslint/js'
import jsdoc from 'eslint-plugin-jsdoc'
import reactCompiler from 'eslint-plugin-react-compiler'
import reactPlugin from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'

export default [
  js.configs.recommended,
  jsdoc.configs['flat/recommended'],
  {
    files: ['**/*.{js,jsx}'],
    plugins: {
      react: reactPlugin,
      'react-compiler': reactCompiler,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      jsdoc,
    },
    languageOptions: {
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      ...reactPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react-compiler/react-compiler': 'error',
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'warn',
      'react-refresh/only-export-components': 'warn',
      // JSDoc enforcement
      'jsdoc/require-jsdoc': [
        'error',
        {
          publicOnly: true,
          require: {
            FunctionDeclaration: true,
            ArrowFunctionExpression: true,
          },
        },
      ],
      'jsdoc/require-description': 'error',
      'jsdoc/require-param': 'error',
      'jsdoc/require-returns': 'warn',
      'jsdoc/require-param-type': 'off', // react-docgen reads types from
      'jsdoc/require-returns-type': 'off', // PropTypes/TS, not JSDoc @type tags
    },
    settings: {
      react: { version: 'detect' },
      jsdoc: {
        mode: 'typescript',
        preferredTypes: {
          'React.JSX.Element': 'React.JSX.Element',
        },
      },
    },
  },
  {
    files: ['**/*.test.{js,jsx}', '**/test/**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        describe: 'readonly',
        test: 'readonly',
        it: 'readonly',
        expect: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
        vi: 'readonly',
      },
    },
    rules: {
      'jsdoc/require-jsdoc': 'off', // don't require JSDoc on test functions
    },
  },
]
