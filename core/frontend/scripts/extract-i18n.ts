import { spawnSync } from 'child_process'
import {
  existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync,
} from 'fs'
import { tmpdir } from 'os'
import {
  dirname, extname, join, relative,
} from 'path'
import ts from 'typescript'
import { compileTemplate, parseComponent } from 'vue/compiler-sfc'

const frontend_root = join(import.meta.dir, '..')
const src_root = join(frontend_root, 'src')
const i18n_dir = join(src_root, 'i18n')
const english_po_path = join(i18n_dir, 'en.po')
const ttag_bin = join(frontend_root, 'node_modules', '.bin', 'ttag')
const ignored_directories = new Set(['vue-tour', 'node_modules'])
const ttag_discover_args = [
  '--discover', 't',
  '--discover', 'gettext',
  '--discover', 'ngettext',
  '--discover', 'jt',
]

interface TemplateNode {
  type?: number
  expression?: string
  directives?: { value?: string }[]
  ifConditions?: { exp?: string, block: TemplateNode }[]
  children?: TemplateNode[]
  scopedSlots?: Record<string, TemplateNode>
}

function walkFiles(directory: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      if (!ignored_directories.has(entry.name)) {
        files.push(...walkFiles(path))
      }
      continue
    }
    files.push(path)
  }
  return files.sort()
}

function collectTemplateExpressions(node: TemplateNode | undefined, expressions: string[]): void {
  if (!node) {
    return
  }
  if (node.type === 2 && node.expression) {
    expressions.push(node.expression)
  }
  if (node.directives) {
    for (const directive of node.directives) {
      if (directive.value) {
        expressions.push(directive.value)
      }
    }
  }
  if (node.ifConditions) {
    for (const condition of node.ifConditions) {
      if (condition.exp) {
        expressions.push(condition.exp)
      }
      if (condition.block !== node) {
        collectTemplateExpressions(condition.block, expressions)
      }
    }
  }
  if (node.scopedSlots) {
    for (const slot of Object.values(node.scopedSlots)) {
      collectTemplateExpressions(slot, expressions)
    }
  }
  if (node.children) {
    for (const child of node.children) {
      collectTemplateExpressions(child, expressions)
    }
  }
}

function isTtagIdentifier(name: string): boolean {
  return name === 't' || name === 'gettext' || name === 'ngettext' || name === 'jt' || name === '_'
}

function isTtagTag(node: ts.Node): boolean {
  if (ts.isIdentifier(node)) {
    return isTtagIdentifier(node.text)
  }
  if (ts.isPropertyAccessExpression(node)) {
    return isTtagIdentifier(node.name.text)
  }
  return false
}

function containsTtag(expression: string): boolean {
  const source = ts.createSourceFile(
    'expression.ts',
    `(${expression})`,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  )
  let found = false
  function visit(node: ts.Node): void {
    if (found) {
      return
    }
    if (ts.isTaggedTemplateExpression(node) && isTtagTag(node.tag)) {
      found = true
      return
    }
    if (ts.isCallExpression(node) && isTtagTag(node.expression)) {
      found = true
      return
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

function transpileTypeScript(source: string, filename: string): string {
  return ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2020,
      module: ts.ModuleKind.ESNext,
      experimentalDecorators: true,
    },
    fileName: filename,
  }).outputText
}

function javascriptFromVue(source: string, filename: string): string {
  const descriptor = parseComponent(source, { filename })
  const parts: string[] = []
  if (descriptor.template?.content) {
    const compiled = compileTemplate({
      source: descriptor.template.content,
      filename,
      id: filename,
    })
    if (compiled.errors.length > 0) {
      throw new Error(`Failed to compile template ${filename}: ${compiled.errors.join('\n')}`)
    }
    const expressions: string[] = []
    collectTemplateExpressions(compiled.ast as TemplateNode | undefined, expressions)
    const ttag_expressions = expressions.filter(containsTtag)
    if (ttag_expressions.length > 0) {
      parts.push(ttag_expressions.map((expression) => `void (${expression})`).join('\n'))
    }
  }
  const script = descriptor.script ?? descriptor.scriptSetup
  if (script?.content) {
    const script_source = script.lang === 'ts'
      ? transpileTypeScript(script.content, filename)
      : script.content
    parts.push(script_source)
  }
  return parts.join('\n')
}

function javascriptFromFile(path: string): string {
  const source = readFileSync(path, 'utf8')
  if (extname(path) === '.vue') {
    return javascriptFromVue(source, path)
  }
  return transpileTypeScript(source, path)
}

function shouldExtract(path: string): boolean {
  if (path.endsWith('.d.ts')) {
    return false
  }
  if (path.startsWith(i18n_dir)) {
    return false
  }
  const extension = extname(path)
  return extension === '.vue' || extension === '.ts'
}

function runTtag(args: string[]): void {
  const result = spawnSync(ttag_bin, args, {
    cwd: frontend_root,
    stdio: 'inherit',
  })
  if (result.status !== 0) {
    throw new Error(`ttag ${args.join(' ')} failed`)
  }
}

function rewriteCatalogPaths(content: string, staging_root: string): string {
  const prefix = staging_root.endsWith('/') ? staging_root : `${staging_root}/`
  return content
    .replaceAll(prefix, '')
    .replaceAll('.vue.js', '.vue')
    .replaceAll('.ts.js', '.ts')
}

function stabilizeCatalog(content: string): string {
  return content
    .replace(/POT-Creation-Date: .*\\n/g, 'POT-Creation-Date: YEAR-MO-DA HO:MI+ZONE\\n')
    .replace(/PO-Revision-Date: .*\\n/g, 'PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n')
}

function ensureLanguageHeader(content: string, language: string): string {
  if (content.includes(`Language: ${language}`)) {
    return content
  }
  return content.replace(
    '"Content-Type: text/plain; charset=utf-8\\n"\n',
    `"Content-Type: text/plain; charset=utf-8\\n"\n"Language: ${language}\\n"\n`,
  )
}

function englishCatalogText(content: string, staging_root: string): string {
  return ensureLanguageHeader(stabilizeCatalog(rewriteCatalogPaths(content, staging_root)), 'en')
}

function showCatalogDiff(committed: string, extracted: string): void {
  const diff_root = mkdtempSync(join(tmpdir(), 'blueos-i18n-diff-'))
  try {
    const committed_path = join(diff_root, 'committed.po')
    const extracted_path = join(diff_root, 'extracted.po')
    writeFileSync(committed_path, committed)
    writeFileSync(extracted_path, extracted)
    spawnSync('diff', ['-u', '--label', 'src/i18n/en.po', '--label', 'extracted', committed_path, extracted_path], {
      stdio: 'inherit',
    })
  } finally {
    rmSync(diff_root, { recursive: true, force: true })
  }
}

function checkEnglishCatalog(extracted: string): void {
  const relative_english = relative(frontend_root, english_po_path)
  if (!existsSync(english_po_path)) {
    console.error(`${relative_english} is missing.`)
    console.error('Run `bun run i18n:extract` and commit src/i18n/en.po.')
    process.exitCode = 1
    return
  }
  const committed = stabilizeCatalog(readFileSync(english_po_path, 'utf8'))
  if (committed === extracted) {
    console.log(`${relative_english} is up to date`)
    return
  }
  console.error(`${relative_english} is out of date.`)
  console.error('Run `bun run i18n:extract` and commit src/i18n/en.po.')
  showCatalogDiff(committed, extracted)
  process.exitCode = 1
}

function extractSources(check = false): void {
  const staging_root = mkdtempSync(join(tmpdir(), 'blueos-i18n-'))
  const check_output_path = check ? join(tmpdir(), `blueos-i18n-check-${process.pid}.po`) : undefined
  try {
    const staged_files: string[] = []
    for (const path of walkFiles(src_root).filter(shouldExtract)) {
      const javascript = javascriptFromFile(path)
      if (!javascript.trim()) {
        continue
      }
      const staged_path = join(staging_root, `${relative(frontend_root, path)}.js`)
      mkdirSync(dirname(staged_path), { recursive: true })
      writeFileSync(staged_path, javascript)
      staged_files.push(staged_path)
    }
    if (staged_files.length === 0) {
      throw new Error('No source files found for extraction')
    }
    if (!check) {
      mkdirSync(i18n_dir, { recursive: true })
    }
    const output_path = check_output_path ?? english_po_path
    runTtag([
      'extract',
      '--numberedExpressions',
      '--sortByMsgid',
      '--extractLocation',
      'file',
      ...ttag_discover_args,
      '-o',
      output_path,
      staging_root,
    ])
    const extracted = englishCatalogText(readFileSync(output_path, 'utf8'), staging_root)
    if (check) {
      checkEnglishCatalog(extracted)
      return
    }
    writeFileSync(english_po_path, extracted)
    console.log(`Extracted translations from ${staged_files.length} files`)
    console.log(`Wrote ${relative(frontend_root, english_po_path)}`)
  } finally {
    rmSync(staging_root, { recursive: true, force: true })
    if (check_output_path) {
      rmSync(check_output_path, { force: true })
    }
  }
}

extractSources(process.argv.includes('--check'))
