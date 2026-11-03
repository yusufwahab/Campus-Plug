import sharp from "sharp";

const mark = (pad) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="512" height="512">
<rect width="40" height="40" fill="#163A2C"/>
<g transform="translate(${pad} ${pad}) scale(${1 - (pad * 2) / 40})">
<path d="M14 9v7M26 9v7" stroke="#C9F26C" stroke-width="3" stroke-linecap="round"/>
<path d="M11 16h18v4a9 9 0 0 1-9 9 9 9 0 0 1-9-9z" fill="#C9F26C"/>
<path d="M20 29v4" stroke="#C9F26C" stroke-width="3" stroke-linecap="round"/></g></svg>`;

for (const [file, size, pad] of [["icon-192", 192, 4], ["icon-512", 512, 4], ["maskable-512", 512, 8], ["apple-touch-icon", 180, 4]]) {
  await sharp(Buffer.from(mark(pad))).resize(size, size).png().toFile(`public/icons/${file}.png`);
}
