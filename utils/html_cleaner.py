import re
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin


def clean_html(raw_html: str, base_url: str) -> str:
    """Strip non-content elements from HTML and resolve relative URLs.

    Removes: scripts, styles, SVG data, comments, tracking pixels,
    noscript blocks, and other non-content elements.

    Resolves: relative URLs in href, src, action attributes to absolute.
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove script tags
    for tag in soup.find_all("script"):
        tag.decompose()

    # Remove style tags (external stylesheets via <link> are kept)
    for tag in soup.find_all("style"):
        tag.decompose()

    # Remove noscript blocks
    for tag in soup.find_all("noscript"):
        tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove tracking pixels (1x1 images)
    for img in soup.find_all("img"):
        width = img.get("width", "")
        height = img.get("height", "")
        if str(width).strip() in ("0", "1") and str(height).strip() in ("0", "1"):
            img.decompose()

    # Remove only large inline SVGs (data blobs), keep small icon SVGs
    for svg in soup.find_all("svg"):
        svg_str = str(svg)
        if len(svg_str) > 2000:  # Large SVGs are decorative blobs, strip them
            svg.decompose()

    # Remove iframe embeds (tracking, ads, third-party widgets)
    for iframe in soup.find_all("iframe"):
        iframe.decompose()

    # Resolve relative URLs to absolute
    for tag in soup.find_all(True):
        for attr in ("href", "src", "action"):
            val = tag.get(attr)
            if val and isinstance(val, str) and not val.startswith(("http://", "https://", "data:", "mailto:", "tel:", "javascript:", "#")):
                tag[attr] = urljoin(base_url + "/", val)

    # Resolve relative URLs in <link> stylesheet references
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href and not href.startswith(("http://", "https://", "data:")):
            link["href"] = urljoin(base_url + "/", href)

    # Strip excessive whitespace but keep structure
    html_str = str(soup)
    html_str = re.sub(r"\n\s*\n\s*\n", "\n\n", html_str)

    return html_str


def extract_text_content(html: str) -> str:
    """Extract visible text content from HTML for analysis.

    Returns a clean text representation with section markers.
    """
    soup = BeautifulSoup(html, "html.parser")

    sections = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "a", "button", "span", "li", "label"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 1:
            tag_name = tag.name.upper()
            if tag.name == "a":
                href = tag.get("href", "")
                sections.append(f"[{tag_name} href={href}] {text}")
            elif tag.name == "button":
                sections.append(f"[BUTTON] {text}")
            else:
                sections.append(f"[{tag_name}] {text}")

    return "\n".join(sections)
