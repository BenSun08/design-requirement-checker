// Graphviz runs only at build time. No WASM or JavaScript ships in the pack.
import {readFile, writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const [modulePath, input, output] = process.argv.slice(2);
const {instance} = await import(pathToFileURL(modulePath).href);
const viz = await instance();
await writeFile(output, viz.renderString(await readFile(input, 'utf8'), {format: 'svg'}));
