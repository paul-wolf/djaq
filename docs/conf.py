import datetime
import os
import sys

import sphinx_rtd_theme

extensions = [
    "sphinx_rtd_theme",
]


project = "djaq"
copyright = "2021, Paul Wolf"
author = "Paul Wolf"
copyright = f"2017-{datetime.datetime.utcnow().year}, {author}"

release = "0.1.0"

templates_path = ["_templates"]

exclude_patterns = ["readme.rst", ".venv", "_build", "Thumbs.db", ".DS_Store"]


html_theme = "sphinx_rtd_theme"

html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

html_static_path = ["_static"]


html_theme_options = {
    "analytics_anonymize_ip": False,
    #  "logo_only": False,
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
    "vcs_pageview_mode": "",
    #  "style_nav_header_background": "white",
    # Toc options
    "collapse_navigation": True,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}