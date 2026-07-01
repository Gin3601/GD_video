module.exports = {
  root: true,
  env: {
    node: true,
    es2022: true,
  },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    project: './tsconfig.json',
  },
  plugins: ['@typescript-eslint'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier',
  ],
  rules: {
    // 禁止空 catch 块
    'no-empty': ['error', { allowEmptyCatch: false }],
    // 要求使用 const 声明不会被修改的变量
    'prefer-const': 'error',
    // 禁止未使用的变量
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    // 要求显式的返回类型
    '@typescript-eslint/explicit-function-return-type': 'off',
    // 允许 any 类型（部分场景需要）
    '@typescript-eslint/no-explicit-any': 'warn',
    // 禁止使用 console（允许 console.error 用于日志）
    'no-console': ['warn', { allow: ['error'] }],
  },
  ignorePatterns: ['dist/', 'node_modules/', '*.js', '*.cjs'],
};
