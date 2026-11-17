function detectObjectShift(canvas, imgBefore, imgAfter, threshold = 45) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  ctx.drawImage(imgBefore, 0, 0, w, h);
  const data1 = ctx.getImageData(0, 0, w, h).data;

  ctx.drawImage(imgAfter, 0, 0, w, h);
  const data2 = ctx.getImageData(0, 0, w, h).data;

  const step = 12;
  ctx.strokeStyle = '#00f0ff';
  ctx.lineWidth = 2;

  for (let y = 0; y < h; y += step) {
    for (let x = 0; x < w; x += step) {
      const i = (y * w + x) * 4;
      
      const diff = Math.abs(data1[i] - data2[i]) +
                   Math.abs(data1[i + 1] - data2[i + 1]) +
                   Math.abs(data1[i + 2] - data2[i + 2]);

      if (diff > threshold) {
        ctx.strokeRect(x - 6, y - 6, 20, 20);
      }
    }
  }
}
