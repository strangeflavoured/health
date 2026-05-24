.. HealthAnalyser documentation master file, created by
   sphinx-quickstart on Sun Apr 19 15:39:45 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

HealthAnalyser Documentation
============================

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Project

   changelog
   contributing
   maintainers

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Notes:

   Getting Started <getting-started>
   Using Redis & Docker <docker-redis>
   Dev tools <dev-tools>
   Dev workflow <dev-workflow>
   Pass secrets <pass-secrets>

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Security & CI:

   Security <security>
   Threat model <threat-model>
   CI/CD workflows <ci-cd>

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: API References:

   src/modules
   backend/modules
   react_autodoc/index

.. include:: ../../README.md
   :parser: myst_parser.sphinx_


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
