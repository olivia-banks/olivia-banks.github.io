import datetime
import os
import re
import pathlib
import shutil
import yaml
import smartypants
import mistune
from mistune.toc import add_toc_hook, render_toc_ul
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import html
from jinja2 import Environment, FileSystemLoader
from urllib.parse import quote

CONTENT_DIR = "content"
OUTPUT_DIR = "dist"
TEMPLATES_DIR = "templates"

QUOTE_RE = re.compile(r'(?:"([^"]+)"|“([^”]+)”)', re.UNICODE | re.MULTILINE)
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL | re.MULTILINE)


class CustomRenderer(mistune.HTMLRenderer):
    def __init__(self):
        super().__init__(escape=False)

    def block_code(self, code, info=None):
        if info:
            try:
                lexer = get_lexer_by_name(info, stripall=True)
            except Exception:
                lexer = get_lexer_by_name("text", stripall=True)
            formatter = html.HtmlFormatter()
            return highlight(code, lexer, formatter)

        return "<pre><code>" + mistune.escape(code) + "</code></pre>"

    def text(self, text):
        def replacer(m):
            # Group 1 = straight quotes, group 2 = curly quotes
            inner = m.group(1) or m.group(2)
            return f"<q>{inner}</q>"

        return QUOTE_RE.sub(replacer, text)


def postprocess_html_fragment(text: str) -> str:
    text = re.sub(COMMENT_RE, "", text)
    text = smartypants.smartypants(text)

    return text


def parse_markdown_with_metadata(md_path):
    with open(md_path, "r") as f:
        text = f.read()

    metadata = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            _, yaml_block, body = parts
            metadata = yaml.safe_load(yaml_block) or {}

            required = ["title", "date", "description", "tags"]
            if not all(key in metadata for key in required):
                raise ValueError(f"Missing required metadata in {md_path}")

            metadata["date"] = datetime.datetime.strptime(metadata["date"], "%Y-%m-%d")

    html_content, render_state = render_markdown.parse(body.strip())
    return metadata, html_content, render_state


def calculate_output_path(md_path):
    rel_path = pathlib.Path(md_path).relative_to(CONTENT_DIR)
    parts = list(rel_path.parts)
    stem = pathlib.Path(parts[-1]).stem

    if len(parts) == 1:
        output_path = pathlib.Path(OUTPUT_DIR) / (stem + ".html")
    else:
        output_path = (
            pathlib.Path(OUTPUT_DIR) / pathlib.Path(*parts[:-1]) / (stem + ".html")
        )

    return output_path


def create_markdown_registry():
    registry = {}

    print("Building markdown registry...")

    for root, dirs, files in os.walk(CONTENT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for file in files:
            if file.startswith(".") or not file.endswith(".md"):
                continue

            file_path = os.path.join(root, file)

            try:
                with open(file_path, "r") as f:
                    text = f.read()

                metadata = {}
                body = text

                if text.startswith("---"):
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        _, yaml_block, body = parts
                        metadata = yaml.safe_load(yaml_block) or {}

                output_path = calculate_output_path(file_path)

                if metadata.get("draft", False):
                    print(f"Skipping draft: {file_path}")
                    continue

                registry[file_path] = {
                    "source_path": file_path,
                    "output_path": output_path,
                    "metadata": metadata,
                    "raw_body": body,
                }

                print(f"Registered: {file_path}")

            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue

    print(f"Registry complete. Found {len(registry)} markdown files.")
    return registry


def get_from_registry(registry, startswith):
    posts = []

    for v in registry.values():
        is_index_file = v["source_path"].endswith("index.md")

        if v["source_path"].startswith(startswith) and not is_index_file:
            posts.append(v)

    posts.sort(key=lambda x: x["metadata"]["date"], reverse=True)
    return posts


def post_url(post):
    return post["output_path"].relative_to(OUTPUT_DIR)


def render_registry_to_files(registry, template_env):
    print("Rendering files to disk...")

    template = template_env.get_template("base.html")
    rendered_count = 0

    for file_path, file_data in registry.items():
        output_path = file_data["output_path"]
        print(f"Rendering {file_path} -> {output_path}")

        template_param_pack = {
            "title": file_data["metadata"]["title"],
            "meta": file_data["metadata"],
            "rendered_on": datetime.datetime.now(),
            "registry": registry,
        }

        expanded_body = template_env.from_string(file_data["raw_body"]).render(
            **template_param_pack
        )

        _, render_state = render_markdown.parse(expanded_body.strip())
        content_html = render_markdown(expanded_body.strip())
        assert isinstance(content_html, str)

        content_html = postprocess_html_fragment(content_html)
        toc = render_toc_ul(render_state.env["toc_items"])

        html = template.render(content=content_html, toc=toc, **template_param_pack)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(html)

        rendered_count += 1

    print(f"Rendering complete. {rendered_count} files rendered.")


def copy_all_files():
    print("Copying all files...")

    copied_count = 0

    for root, dirs, files in os.walk(CONTENT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for file in files:
            if file.startswith("."):
                continue

            file_path = os.path.join(root, file)
            try:
                rel_path = pathlib.Path(file_path).relative_to(CONTENT_DIR)
                output_path = pathlib.Path(OUTPUT_DIR) / rel_path

                print(f"Copied {file_path} -> {output_path}")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, output_path)
                copied_count += 1

            except Exception as e:
                print(f"Error copying {file_path}: {e}")
                continue

    print(f"Copy complete. {copied_count} files copied.")


def build_site():
    print("Starting site build...")

    template_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template_env.globals.update(get_from_registry=get_from_registry, post_url=post_url)

    markdown_registry = create_markdown_registry()

    render_registry_to_files(markdown_registry, template_env)

    copy_all_files()

    print("Site build complete!")
    return markdown_registry


if __name__ == "__main__":
    global renderer, render_markdown

    renderer = CustomRenderer()
    render_markdown = mistune.create_markdown(renderer=renderer, escape=False)
    add_toc_hook(
        render_markdown,
        heading_id=lambda data, number: quote(data["text"].lower().replace(" ", "-")),
    )

    registry = build_site()
