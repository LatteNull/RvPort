/** @type {import('prettier').Config} */
const config = {
  // 每行最大字符数，超出会自动换行
  printWidth: 100,

  // 缩进空格数
  tabWidth: 2,

  // 语句末尾是否加分号
  semi: false,

  // 使用单引号而非双引号
  singleQuote: true,

  // 多行结构末尾是否加尾逗号（all = 尽可能都加）
  trailingComma: 'none',

  // 箭头函数单参数时是否保留括号：(x) => x
  arrowParens: 'always',

  // 对象字面量大括号内是否加空格：{ foo: bar }
  bracketSpacing: true
}

export default config
