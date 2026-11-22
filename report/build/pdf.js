// HTML을 A4 PDF로 변환한다. 사용: node pdf.js <input.html> <output.pdf>
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [input, output] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(input), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({
    path: output,
    format: 'A4',
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate:
      '<div style="width:100%;font-size:8px;color:#7F7F7F;padding:0 18mm;display:flex;justify-content:space-between;font-family:Pretendard,sans-serif;">' +
      '<span>반도체 생산관리 세부직무 분석</span>' +
      '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
  });
  await browser.close();
})();
