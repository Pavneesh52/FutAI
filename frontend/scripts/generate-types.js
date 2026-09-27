import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')

async function main() {
  const schemaPath = path.resolve(frontendRoot, 'openapi.json')
  const outDir = path.resolve(frontendRoot, 'src', 'types')
  const outFile = path.resolve(outDir, 'api.ts')

  if (!fs.existsSync(schemaPath)) {
    console.error(
      `Error: ${schemaPath} does not exist. Run python scripts/export_openapi.py first.`,
    )
    process.exit(1)
  }

  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true })
  }

  console.log(`Generating types from ${schemaPath}...`)
  const fileUrl = pathToFileURL(schemaPath)
  const ast = await openapiTS(fileUrl)
  const contents = astToString(ast)
  fs.writeFileSync(outFile, contents, 'utf8')
  console.log(`Wrote generated types to ${outFile}`)
}

main().catch((err) => {
  console.error('Failed to generate types:', err)
  process.exit(1)
})
