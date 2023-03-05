# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from sphinx.application import Sphinx

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "berconpy"
copyright = "2022, thegamecracks"
author = "thegamecracks"
release = "1.0.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx_autodoc_typehints",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = []

# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#configuration
autodoc_default_options = {
    "members": True
}
autodoc_member_order = "groupwise"

# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static"]
html_css_files = []
html_theme_options = {
    "description": "Bringing the almighty event loop to your remote console",
    "github_button": True,
    "github_repo": "berconpy",
    "github_user": "thegamecracks",
}


def skip_init(app: Sphinx, what: str, name: str, obj, skip: bool, options):
    # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#event-autodoc-skip-member
    if what == "method" and name == "__init__":
        return True


def setup(app: Sphinx):
    app.connect("autodoc-skip-member", skip_init)
