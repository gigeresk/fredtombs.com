// Click an image to see it full screen; click again (or press Esc) to close.
// Uses the theme's .lightbox styles. Images inside links are left alone so
// thumbnails still navigate, and book covers are too small to be worth zooming.
(() => {
  let box = null;

  const close = () => {
    if (!box) return;
    box.remove();
    box = null;
    document.documentElement.classList.remove("lightbox-open");
  };

  const open = (img) => {
    box = document.createElement("div");
    box.className = "lightbox open";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-label", img.alt || "Enlarged image");
    const big = document.createElement("img");
    big.src = img.currentSrc || img.src;
    big.alt = img.alt;
    box.append(big);
    box.addEventListener("click", close);
    document.body.append(box);
    document.documentElement.classList.add("lightbox-open");
  };

  const zoomable = (img) => !img.closest("a, .lightbox, ul.books");

  document.addEventListener("click", (e) => {
    const img = e.target.closest("img");
    if (img && zoomable(img)) open(img);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });

  const mark = () =>
    document.querySelectorAll("main img").forEach((img) => {
      if (zoomable(img)) img.classList.add("zoomable");
    });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mark);
  else mark();
})();
