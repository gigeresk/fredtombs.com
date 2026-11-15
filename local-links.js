// Nav links are root-relative ("/", "/#books") so the live site shows plain
// fredtombs.com. Opened straight from disk, "/" would mean the filesystem
// root, so point them at index.html instead. Does nothing when served.
if (location.protocol === "file:") {
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('nav a[href^="/"]').forEach((a) => {
      a.setAttribute("href", "index.html" + a.getAttribute("href").slice(1));
    });
  });
}
