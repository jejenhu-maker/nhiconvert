// 從 HTML 抽出 core 與 UI 兩段 script，供 Node 測試使用
// 用法：node tests/extract-core.js 健保申報轉CSV工具.html out/
const fs = require("fs"), path = require("path");
const [html, outDir] = process.argv.slice(2);
const s = fs.readFileSync(html, "utf-8");
const blocks = [...s.matchAll(/<script(?: id="core")?>([\s\S]*?)<\/script>/g)].map(m => m[1]);
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "core.js"), blocks[0]);
fs.writeFileSync(path.join(outDir, "ui.js"), blocks[1]);
console.log("extracted core.js / ui.js to", outDir);
