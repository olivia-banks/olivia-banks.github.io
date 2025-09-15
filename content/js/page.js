function redirectToMarkdown() {
  let path = window.location.pathname;

  if (path.endsWith("/")) {
    path += "index.html";
  }

  const markdownPath = path.replace(/\.html$/, ".md");

  window.location.assign(markdownPath);
}

window.onload = function () {
  const only_script_elements = document.getElementsByClassName("only-script");

  for (const element of only_script_elements) {
    element.hidden = false;
  }
};
