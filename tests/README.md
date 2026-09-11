# 測試

需要 Node 24 以上，以及放在 `../申報資料/` 的申報檔（不會上傳）。

```
node tests/extract-core.js 健保申報轉CSV工具.html out
node tests/node-test.js out/core.js 申報資料 out
node tests/node-test-per-source.js out/core.js 申報資料
```

`chrome-core-test.html` 與 `chrome-ui-test.html` 需搭配本機 http 伺服器（同目錄放 core.js、tool.html、a.zip、b.zip）並用 `chrome --headless=new --dump-dom` 執行。
